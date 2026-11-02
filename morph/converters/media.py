"""Video, audio, GIF and subtitle conversions — all powered by FFmpeg."""
import re
import subprocess

from core import tools
from core.registry import GROUPS, ConversionError, converter
from core.util import CREATE_NO_WINDOW, run

TRIM = ["trim_start", "trim_end"]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def probe(path):
    """Read duration and streams from FFmpeg's banner (so ffprobe isn't needed)."""
    try:
        r = subprocess.run([tools.ffmpeg(), "-hide_banner", "-nostdin", "-i", str(path)],
                           capture_output=True, text=True, errors="replace", timeout=60,
                           creationflags=CREATE_NO_WINDOW)
        err = r.stderr
    except Exception:
        err = ""
    info = {"duration": None, "video": False, "audio": False, "subs": [], "fps": None, "height": None}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if m:
        info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) or None
    for line in err.splitlines():
        if "Stream #" not in line:
            continue
        if ": Video:" in line and "(attached pic)" not in line:
            info["video"] = True
            size = re.search(r", (\d{2,5})x(\d{2,5})", line)
            if size and not info["height"]:
                info["height"] = int(size.group(2))
            fps = re.search(r", ([\d.]+) fps", line)
            if fps and not info["fps"]:
                info["fps"] = float(fps.group(1))
        elif ": Audio:" in line:
            info["audio"] = True
        elif ": Subtitle:" in line:
            codec = re.search(r": Subtitle: (\w+)", line)
            info["subs"].append(codec.group(1) if codec else "unknown")
    if "Invalid data found" in err or ("Duration" not in err and not (info["video"] or info["audio"] or info["subs"])):
        raise ConversionError("This file doesn't look like a media file FFmpeg can read. It may be damaged.")
    return info


def trim_args(ctx, info):
    start, end = ctx.opts.get("trim_start"), ctx.opts.get("trim_end")
    if start is not None and end is not None and end <= start:
        raise ConversionError("The end time needs to be after the start time.")
    dur = info.get("duration")
    if start and dur and start >= dur:
        raise ConversionError("The start time is past the end of the file.")
    pre = ["-ss", f"{start:.3f}"] if start else []
    post = ["-t", f"{end - (start or 0):.3f}"] if end else []
    if end:
        new_dur = min(end, dur or end) - (start or 0)
    elif dur:
        new_dur = dur - (start or 0)
    else:
        new_dur = None
    return pre, post, new_dur


def ffmpeg(ctx, args, duration, label="Converting"):
    cmd = [tools.ffmpeg(), "-hide_banner", "-nostdin", "-y", "-progress", "pipe:1", "-nostats", *args]

    def on_line(line):
        if line.startswith(("out_time_us=", "out_time_ms=")) and duration:
            try:
                secs = int(line.split("=", 1)[1]) / 1_000_000
            except ValueError:
                return
            ctx.progress(min(0.99, secs / duration), f"{label}… {int(min(1, secs / duration) * 100)}%")

    ctx.progress(0.0 if duration else None, f"{label}…")
    run(cmd, ctx, on_line=on_line, friendly="FFmpeg couldn't convert this file.")


def audio_filters(ctx):
    af = []
    vol = ctx.opts.get("volume")
    if vol is not None and abs(vol - 100) > 0.5:
        af.append(f"volume={vol / 100:.2f}")
    if ctx.opts.get("normalize"):
        af.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    return ["-af", ",".join(af)] if af else []


# --------------------------------------------------------------------------
# Video -> video
# --------------------------------------------------------------------------

VIDEO_CONTAINER = {
    "mp4": ("x264", "aac"), "m4v": ("x264", "aac"), "mov": ("x264", "aac"), "mkv": ("x264", "aac"),
    "flv": ("x264", "aac"), "ts": ("x264", "aac"), "3gp": ("x264", "aac"), "webm": ("vp9", "opus"),
    "avi": ("mpeg4", "mp3"), "wmv": ("wmv2", "wma"), "mpeg": ("mpeg2", "mp2"), "ogv": ("theora", "vorbis"),
}
CODEC_CHOICE = {"mp4", "mkv"}
CRF = {
    "x264": {"best": 18, "high": 21, "balanced": 24, "small": 28},
    "x265": {"best": 20, "high": 23, "balanced": 26, "small": 30},
    "vp9": {"best": 24, "high": 31, "balanced": 36, "small": 42},
    "av1": {"best": 24, "high": 30, "balanced": 36, "small": 42},
    "q": {"best": 2, "high": 3, "balanced": 5, "small": 8},          # mpeg4 / mpeg2 / wmv2 (lower = better)
    "theora": {"best": 9, "high": 7, "balanced": 5, "small": 3},     # higher = better
}
MPEG2_RATES = [23.976, 24, 25, 29.97, 30, 50, 59.94, 60]


def _video_encoder(ctx, codec, q):
    enc = tools.ffmpeg_encoders()
    if codec == "x264":
        return ["-c:v", "libx264", "-preset", "medium" if q == "best" else "veryfast",
                "-crf", str(CRF["x264"][q]), "-pix_fmt", "yuv420p"]
    if codec == "x265":
        if "libx265" not in enc:
            raise ConversionError("Your FFmpeg doesn't include H.265. Pick H.264 instead.")
        tag = ["-tag:v", "hvc1"] if ctx.dst_fmt in ("mp4", "mov", "m4v") else []
        return ["-c:v", "libx265", "-preset", "fast", "-crf", str(CRF["x265"][q]), "-pix_fmt", "yuv420p", *tag]
    if codec == "av1":
        if "libsvtav1" in enc:
            return ["-c:v", "libsvtav1", "-preset", "8", "-crf", str(CRF["av1"][q]), "-pix_fmt", "yuv420p"]
        if "libaom-av1" in enc:
            return ["-c:v", "libaom-av1", "-cpu-used", "6", "-row-mt", "1", "-crf", str(CRF["av1"][q]),
                    "-b:v", "0", "-pix_fmt", "yuv420p"]
        raise ConversionError("Your FFmpeg doesn't include an AV1 encoder. Pick H.264 instead.")
    if codec == "vp9":
        return ["-c:v", "libvpx-vp9", "-crf", str(CRF["vp9"][q]), "-b:v", "0", "-deadline", "good",
                "-cpu-used", "4", "-row-mt", "1", "-pix_fmt", "yuv420p"]
    if codec == "mpeg4":
        tag = ["-vtag", "xvid"]
        return ["-c:v", "mpeg4", *tag, "-q:v", str(CRF["q"][q]), "-pix_fmt", "yuv420p"]
    if codec == "wmv2":
        return ["-c:v", "wmv2", "-q:v", str(CRF["q"][q]), "-pix_fmt", "yuv420p"]
    if codec == "mpeg2":
        return ["-c:v", "mpeg2video", "-q:v", str(CRF["q"][q]), "-pix_fmt", "yuv420p"]
    if codec == "theora":
        return ["-c:v", "libtheora", "-q:v", str(CRF["theora"][q]), "-pix_fmt", "yuv420p"]
    raise ConversionError("Unknown video codec.")


def _audio_encoder_for_video(acodec):
    return {
        "aac": ["-c:a", "aac", "-b:a", "192k"], "opus": ["-c:a", "libopus", "-b:a", "160k"],
        "mp3": ["-c:a", "libmp3lame", "-b:a", "192k"], "wma": ["-c:a", "wmav2", "-b:a", "192k"],
        "mp2": ["-c:a", "mp2", "-b:a", "224k", "-ar", "48000"], "vorbis": ["-c:a", "libvorbis", "-q:a", "5"],
    }[acodec]


def video_options(src, dst):
    base = ["resolution", "vquality"]
    if dst in CODEC_CHOICE:
        base.append("vcodec")
    return base + ["fps", "mute"] + TRIM


@converter(GROUPS["video_in"] + ["gif"], [d for d in GROUPS["video_out"] if d not in ("ogv", "webm")],
           options=video_options, requires=["ffmpeg", "enc:libx264"], engine="FFmpeg", same=True)
@converter(GROUPS["video_in"] + ["gif"], ["webm"], options=video_options,
           requires=["ffmpeg", "enc:libvpx-vp9"], engine="FFmpeg", same=True)
@converter(GROUPS["video_in"] + ["gif"], ["ogv"], options=video_options,
           requires=["ffmpeg", "enc:libtheora"], engine="FFmpeg", same=True)
def video_to_video(ctx):
    info = probe(ctx.src)
    if not info["video"]:
        raise ConversionError("This file has no video picture in it — try converting it to an audio format instead.")
    pre, post, dur = trim_args(ctx, info)
    vcodec, acodec = VIDEO_CONTAINER[ctx.dst_fmt]
    if ctx.dst_fmt in CODEC_CHOICE:
        vcodec = {"h264": "x264", "h265": "x265", "av1": "av1"}[ctx.opts.get("vcodec", "h264")]
    q = ctx.opts.get("vquality", "high")

    vf = []
    res = ctx.opts.get("resolution", "keep")
    if res != "keep":
        vf.append(f"scale=-2:'min({res},ih)'")
    vf.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
    rate = ctx.opts.get("fps", "keep")
    if ctx.dst_fmt == "mpeg":
        target = float(rate) if rate != "keep" else (info["fps"] or 30)
        rate = str(min(MPEG2_RATES, key=lambda r: abs(r - target)))
        rate = {"23.976": "24000/1001", "29.97": "30000/1001", "59.94": "60000/1001"}.get(rate, rate)
    if rate != "keep":
        vf.append(f"fps={rate}")

    args = [*pre, "-i", str(ctx.src), *post, "-map", "0:V:0"]
    if info["audio"] and not ctx.opts.get("mute"):
        args += ["-map", "0:a:0", *_audio_encoder_for_video(acodec)]
    else:
        args += ["-an"]
    args += ["-vf", ",".join(vf), *_video_encoder(ctx, vcodec, q), "-sn", "-dn"]
    if ctx.dst_fmt in ("mp4", "m4v", "mov", "3gp"):
        args += ["-movflags", "+faststart"]
    if ctx.dst_fmt == "3gp":
        args += ["-profile:v", "baseline", "-level", "3.1"]
    out = ctx.out()
    args += [str(out)]
    ffmpeg(ctx, args, dur, "Encoding video")
    return out


# --------------------------------------------------------------------------
# Anything with sound -> audio
# --------------------------------------------------------------------------

AUDIO_ENC = {
    "mp3": ["-c:a", "libmp3lame"], "aac": ["-c:a", "aac", "-f", "adts"], "m4a": ["-c:a", "aac"],
    "alac": ["-c:a", "alac"], "ogg": ["-c:a", "libvorbis"], "opus": ["-c:a", "libopus"],
    "wma": ["-c:a", "wmav2"], "wav": ["-c:a", "pcm_s16le"], "flac": ["-c:a", "flac"],
    "aiff": ["-c:a", "pcm_s16be"], "ac3": ["-c:a", "ac3"], "mp2": ["-c:a", "mp2"],
    "caf": ["-c:a", "alac"], "mka": ["-c:a", "libopus"], "au": ["-c:a", "pcm_s16be"],
}
LOSSY = {"mp3", "aac", "m4a", "ogg", "opus", "wma", "ac3", "mp2", "mka"}
AUDIO_ENC_REQ = {"mp3": "libmp3lame", "ogg": "libvorbis", "opus": "libopus", "mka": "libopus"}


def audio_options(src, dst):
    opts = ["abitrate"] if dst in LOSSY else []
    return opts + ["samplerate", "channels", "volume", "normalize"] + TRIM


def _audio_route(dst):
    req = ["ffmpeg"] + ([f"enc:{AUDIO_ENC_REQ[dst]}"] if dst in AUDIO_ENC_REQ else [])
    return converter(GROUPS["audio_in"] + GROUPS["video_in"], [dst], options=audio_options,
                     requires=req, engine="FFmpeg", same=True)


def to_audio(ctx):
    info = probe(ctx.src)
    if not info["audio"]:
        raise ConversionError("This file has no sound track to convert.")
    pre, post, dur = trim_args(ctx, info)
    d = ctx.dst_fmt
    args = [*pre, "-i", str(ctx.src), *post, "-map", "0:a:0", "-vn", "-sn", "-dn", *AUDIO_ENC[d]]
    if d in LOSSY:
        br = int(ctx.opts.get("abitrate", "192"))
        if d == "mp2":
            br = min(br, 384)
        args += ["-b:a", f"{br}k"]
    sr = ctx.opts.get("samplerate", "keep")
    if sr != "keep":
        ok = {"opus": {"48000"}, "ac3": {"48000", "44100", "32000"}, "mp2": {"48000", "44100", "32000", "22050"}}
        if d not in ok or sr in ok[d]:
            args += ["-ar", sr]
    ch = ctx.opts.get("channels", "keep")
    if ch != "keep":
        args += ["-ac", ch]
    args += audio_filters(ctx)
    out = ctx.out()
    args.append(str(out))
    ffmpeg(ctx, args, dur, "Converting audio")
    return out


for _d in GROUPS["audio_out"]:
    _audio_route(_d)(to_audio)


# --------------------------------------------------------------------------
# Video -> animated GIF / WebP
# --------------------------------------------------------------------------

@converter(GROUPS["video_in"], ["gif"], options=["gif_fps", "gif_width"] + TRIM, requires=["ffmpeg"], engine="FFmpeg")
def video_to_gif(ctx):
    info = probe(ctx.src)
    if not info["video"]:
        raise ConversionError("This file has no video picture in it.")
    pre, post, dur = trim_args(ctx, info)
    fps = ctx.opts.get("gif_fps", "15")
    width = ctx.opts.get("gif_width", "480")
    scale = f",scale='min({width},iw)':-1:flags=lanczos" if width != "keep" else ""
    vf = (f"fps={fps}{scale},split[a][b];[a]palettegen=stats_mode=diff[p];"
          f"[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle")
    out = ctx.out()
    ffmpeg(ctx, [*pre, "-i", str(ctx.src), *post, "-vf", vf, "-loop", "0", "-an", str(out)], dur, "Making GIF")
    return out


@converter(GROUPS["video_in"] + ["gif"], ["webp"], options=["gif_fps", "gif_width"] + TRIM,
           requires=["ffmpeg", "enc:libwebp_anim"], engine="FFmpeg", priority=-1)
def video_to_webp(ctx):
    info = probe(ctx.src)
    if not info["video"]:
        raise ConversionError("This file has no video picture in it.")
    pre, post, dur = trim_args(ctx, info)
    fps = ctx.opts.get("gif_fps", "15")
    width = ctx.opts.get("gif_width", "480")
    vf = f"fps={fps}" + (f",scale='min({width},iw)':-1:flags=lanczos" if width != "keep" else "")
    out = ctx.out()
    ffmpeg(ctx, [*pre, "-i", str(ctx.src), *post, "-vf", vf, "-c:v", "libwebp_anim", "-quality", "75",
                 "-loop", "0", "-an", str(out)], dur, "Making animated WebP")
    return out


# --------------------------------------------------------------------------
# Subtitles
# --------------------------------------------------------------------------

SUB_OUT = {"srt": ["-c:s", "srt"], "vtt": ["-c:s", "webvtt"], "ass": ["-c:s", "ass"],
           "lrc": ["-c:s", "text", "-f", "lrc"], "ttml": ["-c:s", "ttml", "-f", "ttml"]}


def _srt_time(s):
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h):02}:{int(m):02}:{sec:06.3f}".replace(".", ",")


def _parse_sbv(text):
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        if not lines:
            continue
        m = re.match(r"(\d+):(\d+):(\d+(?:\.\d+)?),(\d+):(\d+):(\d+(?:\.\d+)?)", lines[0].strip())
        if not m:
            continue
        g = [float(x) for x in m.groups()]
        cues.append((g[0] * 3600 + g[1] * 60 + g[2], g[3] * 3600 + g[4] * 60 + g[5], "\n".join(lines[1:])))
    return cues


def _srt_to_sbv(text):
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if idx is None:
            continue
        a, b = [t.strip().replace(",", ".") for t in lines[idx].split("-->")]
        fix = lambda t: re.sub(r"^0?(\d+):", r"\1:", t[:12])  # 00:01:02.500 -> 0:01:02.500
        out.append(f"{fix(a)},{fix(b)}\n" + "\n".join(lines[idx + 1:]))
    return "\n\n".join(out) + "\n"


def _read_text(path):
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp1252", errors="replace")


@converter(["srt", "vtt", "ass", "ssa", "lrc", "smi", "sbv", "ttml"], ["srt", "vtt", "ass", "lrc", "ttml", "sbv"],
           requires=["ffmpeg"], engine="FFmpeg")
def subtitles(ctx):
    src = ctx.src
    # Normalise the input to clean UTF-8 so FFmpeg never trips over encodings.
    text = _read_text(src)
    if ctx.src_fmt == "sbv":
        cues = _parse_sbv(text)
        if not cues:
            raise ConversionError("I couldn't find any captions in this SBV file.")
        text = "\n\n".join(f"{i}\n{_srt_time(a)} --> {_srt_time(b)}\n{t}" for i, (a, b, t) in enumerate(cues, 1)) + "\n"
        src = ctx.tmp("input.srt")
    elif ctx.src_fmt == "ttml":
        raise ConversionError("FFmpeg can write TTML but can't read it yet.")
    else:
        src = ctx.tmp(f"input.{ctx.src_fmt}")
    src.write_text(text, encoding="utf-8")

    if ctx.dst_fmt == "sbv":
        if ctx.src_fmt == "srt" or ctx.src_fmt == "sbv":
            srt_text = text
        else:
            tmp_srt = ctx.tmp("mid.srt")
            run([tools.ffmpeg(), "-hide_banner", "-nostdin", "-y", "-i", src, "-c:s", "srt", tmp_srt], ctx,
                friendly="FFmpeg couldn't read these subtitles.")
            srt_text = tmp_srt.read_text(encoding="utf-8", errors="replace")
        out = ctx.out()
        out.write_text(_srt_to_sbv(srt_text), encoding="utf-8")
        return out

    out = ctx.out()
    run([tools.ffmpeg(), "-hide_banner", "-nostdin", "-y", "-i", src, *SUB_OUT[ctx.dst_fmt], out], ctx,
        friendly="FFmpeg couldn't convert these subtitles.")
    return out


IMAGE_SUBS = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub"}


@converter(["mkv", "mp4", "mov", "webm", "m4v", "ts", "m2ts", "mts", "avi"], ["srt", "vtt", "ass"],
           requires=["ffmpeg"], engine="FFmpeg", priority=-1)
def extract_subtitles(ctx):
    info = probe(ctx.src)
    if not info["subs"]:
        raise ConversionError("This video doesn't have a subtitle track to pull out.")
    text_track = next((i for i, c in enumerate(info["subs"]) if c not in IMAGE_SUBS), None)
    if text_track is None:
        raise ConversionError("This video's subtitles are stored as pictures, so they can't be turned into text.")
    out = ctx.out()
    run([tools.ffmpeg(), "-hide_banner", "-nostdin", "-y", "-i", ctx.src, "-map", f"0:s:{text_track}",
         *SUB_OUT[ctx.dst_fmt], out], ctx, friendly="FFmpeg couldn't extract the subtitles.")
    return out
