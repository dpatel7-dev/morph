"""
YouTube (and 1,000+ other sites) to MP3 / MP4 using yt-dlp.

yt-dlp needs a JavaScript runtime (Deno is the default) to fully support
YouTube — see README.md. Only download videos you have the right to keep.

YouTube often blocks cloud computers (Codespaces, VPS hosts) with "Sign in to
confirm you're not a bot". The fix is a signed-in account's cookies:
  * each visitor can upload their own cookies.txt on the YouTube page, or
  * the server owner can set MORPH_YT_COOKIES=/path/to/cookies.txt,
    MORPH_YT_COOKIES_FROM_BROWSER=firefox (when Morph runs on the same computer
    as the browser), or MORPH_YT_PROXY=http://user:pass@host:port.
"""
import hashlib
import os
import re
from pathlib import Path

from core import tools
from core.registry import Cancelled, ConversionError

AUDIO = {"mp3", "m4a", "wav", "flac", "opus"}
VIDEO = {"mp4", "webm", "mkv"}
URL_RE = re.compile(r"^https?://\S+$", re.I)


class NeedsSignIn(ConversionError):
    """YouTube wants proof of a real, signed-in person (the website then shows the sign-in steps)."""
    code = "needs_cookies"


# --------------------------------------------------------------------------
# Cookies: one private file per visitor, holding only YouTube cookies
# --------------------------------------------------------------------------

COOKIE_DIR = Path(os.environ.get("MORPH_COOKIE_DIR") or Path.home() / ".morph" / "youtube-cookies")
SERVER_COOKIES = os.environ.get("MORPH_YT_COOKIES") or None
COOKIES_FROM_BROWSER = os.environ.get("MORPH_YT_COOKIES_FROM_BROWSER") or None
PROXY = os.environ.get("MORPH_YT_PROXY") or None
SIGNED_IN_NAMES = {"SID", "__Secure-1PSID", "__Secure-3PSID", "SAPISID", "__Secure-3PAPISID", "LOGIN_INFO"}
MAX_COOKIE_BYTES = 2 * 1024 * 1024


def _cookie_path(sid):
    if not sid:
        return None
    return COOKIE_DIR / (hashlib.sha256(sid.encode()).hexdigest()[:40] + ".txt")


def has_cookies(sid):
    p = _cookie_path(sid)
    return bool(p and p.exists())


def save_cookies(sid, raw: bytes):
    """Keep only youtube.com cookies from a Netscape cookies.txt export. Returns how many."""
    if not sid:
        raise ConversionError("Open the Morph website first, then upload your cookies there.")
    if len(raw) > MAX_COOKIE_BYTES:
        raise ConversionError("That file is too big to be a cookies.txt export.")
    text = raw.decode("utf-8-sig", errors="replace")
    keep = []
    for line in text.splitlines():
        line = line.rstrip("\r")
        body = line[len("#HttpOnly_"):] if line.startswith("#HttpOnly_") else line
        if not body or (body.startswith("#") and body is line):
            continue
        parts = body.split("\t")
        if len(parts) != 7:
            continue
        domain = parts[0].lstrip(".").lower()
        if domain == "youtube.com" or domain.endswith(".youtube.com"):
            keep.append(line)
    if not keep:
        raise ConversionError("That file has no YouTube cookies in it. Export the cookies while you're on youtube.com, "
                              "using the Netscape / cookies.txt format.")
    names = {l.split("\t")[5] for l in keep}
    if not names & SIGNED_IN_NAMES:
        raise ConversionError("These YouTube cookies aren't from a signed-in account. Sign in to YouTube first, "
                              "then export them again.")
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(COOKIE_DIR, 0o700)
    except OSError:
        pass
    path = _cookie_path(sid)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("# Netscape HTTP Cookie File\n" + "\n".join(keep) + "\n")
    return len(keep)


def remove_cookies(sid):
    p = _cookie_path(sid)
    if p and p.exists():
        p.unlink()


def status():
    ok = tools.has_module("yt_dlp")
    version = None
    if ok:
        try:
            from yt_dlp.version import __version__ as version
        except Exception:
            pass
    return {"installed": ok, "version": version, "js_runtimes": sorted(tools.js_runtimes()),
            "ffmpeg": bool(tools.ffmpeg()), "server_signin": bool(SERVER_COOKIES or COOKIES_FROM_BROWSER or PROXY)}


class _Log:
    def __init__(self):
        self.errors = []

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        self.errors.append(re.sub(r"\x1b\[[0-9;]*m", "", str(msg)))


def _base(log, sid=None):
    opts = {
        "quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
        "socket_timeout": 20, "retries": 3, "fragment_retries": 3, "windowsfilenames": True,
        "logger": log, "color": {"stderr": "no_color", "stdout": "no_color"},
    }
    if tools.ffmpeg():
        opts["ffmpeg_location"] = tools.ffmpeg()
    rt = tools.js_runtimes()
    if rt:
        opts["js_runtimes"] = {name: {"path": path} for name, path in rt.items()}
    # A visitor's own sign-in wins; otherwise the server owner's settings apply
    if has_cookies(sid):
        opts["cookiefile"] = str(_cookie_path(sid))
    elif SERVER_COOKIES:
        opts["cookiefile"] = SERVER_COOKIES
    elif COOKIES_FROM_BROWSER:
        opts["cookiesfrombrowser"] = (COOKIES_FROM_BROWSER,)
    if PROXY:
        opts["proxy"] = PROXY
    return opts


def _friendly(err, log, sid=None):
    """Turn yt-dlp's error into a plain sentence. Sign-in problems raise NeedsSignIn."""
    text = (str(err) + " " + " ".join(log.errors)).lower().replace("\u2019", "'")
    signed_in = has_cookies(sid) or bool(SERVER_COOKIES or COOKIES_FROM_BROWSER)
    if "sign in to confirm your age" in text or "age-restricted" in text or "inappropriate for some users" in text:
        if signed_in:
            return "This video is age-restricted, and the signed-in account isn't allowed to watch it."
        raise NeedsSignIn("This video is age-restricted. Sign in to YouTube through Morph (steps below) to download it.")
    if "sign in to confirm you" in text and "bot" in text:
        if signed_in:
            raise NeedsSignIn("YouTube still wants a sign-in. Your saved cookies have probably expired: "
                              "export them again and upload the new file.")
        raise NeedsSignIn("YouTube is blocking this server until it shows it's a real person. "
                          "Sign in to YouTube through Morph (steps below), then try again.")
    if "private video" in text:
        return "This video is private."
    if "video unavailable" in text or "not available" in text:
        return "This video isn't available (it may be removed, private, or blocked in your country)."
    if "unsupported url" in text:
        return "That link isn't supported. Paste a link to a single video."
    if "ffmpeg" in text and ("not found" in text or "not installed" in text):
        return "FFmpeg is needed for this. Run: pip install imageio-ffmpeg"
    if "js runtime" in text or "javascript" in text or "n challenge" in text or "signature" in text:
        return ("YouTube needs a JavaScript helper to unlock this video. Install Deno (see the README), "
                "then restart Morph.")
    if "requested format is not available" in text:
        return "That quality isn't available for this video. Pick another one."
    if "http error 429" in text or "too many requests" in text:
        return "YouTube says too many requests. Wait a few minutes and try again."
    msg = (log.errors[-1] if log.errors else str(err)).replace("ERROR: ", "")
    return msg[:300] or "The download failed."


def _require():
    if not tools.has_module("yt_dlp"):
        raise ConversionError("yt-dlp isn't installed yet. Run: pip install -U \"yt-dlp[default]\"")


def info(url, sid=None):
    _require()
    from yt_dlp import YoutubeDL
    url = (url or "").strip()
    if not URL_RE.match(url):
        raise ConversionError("Paste a full link that starts with https://")
    log = _Log()
    opts = _base(log, sid) | {"skip_download": True}
    try:
        with YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)
    except Exception as e:
        raise ConversionError(_friendly(e, log, sid))
    if data.get("_type") in ("playlist", "multi_video"):
        entries = [e for e in (data.get("entries") or []) if e]
        if not entries:
            raise ConversionError("That's a playlist link. Open one video and paste its link instead.")
        data = entries[0]
    formats = data.get("formats") or []
    heights = sorted({f["height"] for f in formats
                      if f.get("height") and f.get("vcodec") not in (None, "none")}, reverse=True)
    thumb = data.get("thumbnail")
    if not thumb and data.get("thumbnails"):
        thumb = data["thumbnails"][-1].get("url")
    return {
        "title": data.get("title") or "Untitled",
        "channel": data.get("channel") or data.get("uploader") or "",
        "duration": data.get("duration"),
        "thumbnail": thumb,
        "views": data.get("view_count"),
        "url": data.get("webpage_url") or url,
        "site": data.get("extractor_key") or "",
        "heights": heights,
        "live": bool(data.get("is_live")),
    }


def _format_for(fmt, quality):
    if fmt in AUDIO:
        return "bestaudio/best"
    h = "" if quality in ("best", "", None) else str(int(quality))
    lim = f"[height<=?{h}]" if h else ""
    if fmt == "mp4":
        if h and int(h) <= 1080:
            # H.264 + AAC first: plays everywhere (phones, Windows, QuickTime)
            return (f"bv*{lim}[vcodec^=avc1]+ba[ext=m4a]/bv*{lim}[ext=mp4]+ba[ext=m4a]/"
                    f"bv*{lim}+ba/b{lim}/b")
        return f"bv*{lim}+ba[ext=m4a]/bv*{lim}+ba/b{lim}/b"
    if fmt == "webm":
        return f"bv*{lim}[ext=webm]+ba[ext=webm]/b{lim}[ext=webm]/bv*{lim}+ba/b"
    return f"bv*{lim}+ba/b{lim}/b"  # mkv takes anything


def download(job, url, fmt, quality, cover, out_dir: Path, sid=None):
    _require()
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadCancelled, DownloadError
    if fmt not in AUDIO | VIDEO:
        raise ConversionError("Unknown format.")
    if not tools.ffmpeg():
        raise ConversionError("FFmpeg is needed to save YouTube audio/video. Run: pip install imageio-ffmpeg")
    url = (url or "").strip()
    if not URL_RE.match(url):
        raise ConversionError("Paste a full link that starts with https://")
    out_dir.mkdir(parents=True, exist_ok=True)
    log = _Log()
    state = {"file": None, "index": 0}

    def hook(d):
        if job.cancelled:
            raise DownloadCancelled("cancelled")
        if d.get("status") == "downloading":
            name = d.get("filename")
            if state["file"] and name != state["file"]:
                state["index"] += 1
            state["file"] = name
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            parts = len((d.get("info_dict") or {}).get("requested_formats") or []) or 1
            frac = (done / total) if total else None
            what = "audio" if fmt in AUDIO else ("video" if state["index"] == 0 and parts > 1 else
                                                  ("audio" if parts > 1 else "video"))
            speed = d.get("speed")
            speed_txt = f" at {speed / 1048576:.1f} MB/s" if speed else ""
            if frac is not None:
                overall = min(0.9, (min(state["index"], parts - 1) + frac) / parts * 0.9)
                job.update(overall, f"Downloading {what} {int(frac * 100)}%{speed_txt}")
            else:
                job.update(None, f"Downloading {what}…{speed_txt}")

    def pp_hook(d):
        if job.cancelled:
            raise DownloadCancelled("cancelled")
        if d.get("status") == "started":
            label = {
                "FFmpegExtractAudio": f"Converting to {fmt.upper()}…", "Merger": "Joining video and sound…",
                "FFmpegMetadata": "Adding title & artist…", "EmbedThumbnail": "Adding cover art…",
                "FFmpegThumbnailsConvertor": "Preparing cover art…",
            }.get(d.get("postprocessor"), "Finishing…")
            job.update(0.93, label)

    opts = _base(log, sid) | {
        "format": _format_for(fmt, quality),
        "outtmpl": {"default": str(out_dir / "%(title).150B.%(ext)s")},
        "progress_hooks": [hook], "postprocessor_hooks": [pp_hook],
        "overwrites": True,
    }
    pps = []
    can_cover = cover and fmt in {"mp3", "m4a", "mp4", "mkv"} | ({"flac", "opus"} if tools.has_module("mutagen") else set())
    if can_cover:
        opts["writethumbnail"] = True
        pps.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})
    if fmt in AUDIO:
        pq = str(quality) if fmt in ("mp3", "m4a", "opus") and str(quality).isdigit() else "0"
        pps.append({"key": "FFmpegExtractAudio", "preferredcodec": fmt, "preferredquality": pq})
    else:
        opts["merge_output_format"] = fmt
    pps.append({"key": "FFmpegMetadata", "add_metadata": True})
    if can_cover:
        pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    opts["postprocessors"] = pps

    job.update(None, "Contacting the site…")
    try:
        with YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=True)
    except DownloadCancelled:
        raise Cancelled()
    except DownloadError as e:
        if job.cancelled:
            raise Cancelled()
        raise ConversionError(_friendly(e, log, sid))
    if data.get("_type") in ("playlist", "multi_video"):
        data = next((e for e in data.get("entries") or [] if e), {})
    final = None
    for item in data.get("requested_downloads") or []:
        p = item.get("filepath")
        if p and Path(p).exists():
            final = Path(p)
    if not final:
        candidates = sorted((p for p in out_dir.iterdir() if p.is_file() and p.suffix.lower() == f".{fmt}"),
                            key=lambda p: p.stat().st_mtime)
        final = candidates[-1] if candidates else None
    if not final:
        raise ConversionError("The download finished but the file couldn't be found.")
    # Tidy up any leftovers (thumbnails, partial streams)
    for p in out_dir.iterdir():
        if p != final and p.is_file():
            p.unlink(missing_ok=True)
    return final
