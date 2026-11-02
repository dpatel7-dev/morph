"""
The catalogue: every file format, every option, and every conversion route.

Converters register themselves with the @converter decorator:

    @converter(["mp4", "mov"], ["mp3", "wav"], options=["abitrate"], requires=["ffmpeg"])
    def my_function(ctx):
        ...           # read ctx.src, write a file, return its path

`build()` then keeps only the routes whose helpers are installed.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import tools

# --------------------------------------------------------------------------
# Formats
# --------------------------------------------------------------------------

CATEGORIES = [
    ("video", "Video"), ("audio", "Audio"), ("image", "Image"), ("vector", "Vector"),
    ("document", "Document"), ("markup", "Markup"), ("spreadsheet", "Spreadsheet"),
    ("presentation", "Presentation"), ("pdf", "PDF"), ("ebook", "E-book"),
    ("data", "Data"), ("archive", "Archive"), ("font", "Font"), ("subtitle", "Subtitle"),
]


@dataclass
class Format:
    key: str
    label: str
    category: str
    ext: str
    name: str = ""


FORMATS: dict[str, Format] = {}
_EXT_TO_KEY: dict[str, str] = {}


def fmt(category, key, label=None, ext=None, name="", aliases=()):
    f = Format(key, label or key.upper(), category, ext or key, name)
    FORMATS[key] = f
    _EXT_TO_KEY.setdefault(f.ext, key)
    _EXT_TO_KEY.setdefault(key, key)
    for a in aliases:
        _EXT_TO_KEY[a] = key


def detect_format(filename: str):
    """'Holiday.TAR.GZ' -> 'tgz', 'photo.jpeg' -> 'jpg'. Returns None if unknown."""
    name = filename.lower()
    for compound in ("tar.gz", "tar.bz2", "tar.xz"):
        if name.endswith("." + compound):
            return _EXT_TO_KEY.get(compound)
    if "." not in name:
        return None
    return _EXT_TO_KEY.get(name.rsplit(".", 1)[1])


# Video
for k, n in [("mp4", "MPEG-4 video"), ("webm", "WebM video"), ("mkv", "Matroska video"),
             ("mov", "QuickTime movie"), ("avi", "AVI video"), ("flv", "Flash video"),
             ("wmv", "Windows Media video"), ("m4v", "iTunes video"), ("mpeg", "MPEG-2 video"),
             ("3gp", "3GPP mobile video"), ("ogv", "Ogg video"), ("ts", "MPEG transport stream")]:
    fmt("video", k, name=n, aliases={"mpeg": ["mpg", "mpe"], "ts": ["m2t"]}.get(k, []))
for k, n in [("mts", "AVCHD video"), ("m2ts", "Blu-ray video"), ("vob", "DVD video"),
             ("f4v", "Flash MP4 video"), ("asf", "ASF video"), ("mxf", "MXF video"),
             ("divx", "DivX video"), ("rmvb", "RealMedia video"), ("dv", "DV video"),
             ("y4m", "YUV4MPEG video"), ("hevc", "Raw HEVC stream")]:
    fmt("video", k, name=n, aliases={"rmvb": ["rm"], "hevc": ["h265"]}.get(k, []))

# Audio
for k, n in [("mp3", "MP3 audio"), ("wav", "WAV audio"), ("flac", "FLAC lossless audio"),
             ("aac", "AAC audio"), ("m4a", "M4A audio"), ("ogg", "Ogg Vorbis audio"),
             ("opus", "Opus audio"), ("wma", "Windows Media audio"), ("aiff", "AIFF audio"),
             ("ac3", "Dolby Digital audio"), ("mp2", "MPEG layer 2 audio"), ("caf", "Core Audio file"),
             ("mka", "Matroska audio"), ("au", "Sun audio")]:
    fmt("audio", k, name=n, aliases={"aiff": ["aif", "aifc"], "ogg": ["oga"], "au": ["snd"]}.get(k, []))
fmt("audio", "alac", "ALAC", ext="m4a", name="Apple lossless (in .m4a)")
for k, n in [("amr", "AMR voice audio"), ("ape", "Monkey's Audio"), ("wv", "WavPack audio"),
             ("dts", "DTS audio"), ("tta", "True Audio"), ("voc", "Creative voice")]:
    fmt("audio", k, name=n)

# Images
for k, n, al in [("png", "PNG image", []), ("jpg", "JPEG image", ["jpeg", "jpe", "jfif"]),
                 ("webp", "WebP image", []), ("avif", "AVIF image", []), ("heic", "HEIC (iPhone) photo", ["heif"]),
                 ("gif", "GIF image", []), ("bmp", "Bitmap image", ["dib"]), ("tiff", "TIFF image", ["tif"]),
                 ("ico", "Windows icon", []), ("icns", "macOS icon", []), ("tga", "Targa image", []),
                 ("jp2", "JPEG 2000 image", ["j2k", "jpf"]), ("ppm", "Netpbm image", ["pgm", "pbm", "pnm"]),
                 ("pcx", "PCX image", []), ("dds", "DirectDraw texture", []), ("psd", "Photoshop file", []),
                 ("qoi", "QOI image", [])]:
    fmt("image", k, name=n, aliases=al)

fmt("vector", "svg", name="SVG vector graphic", aliases=["svgz"])

# Documents (word-processor style)
for k, n in [("docx", "Word document"), ("doc", "Word 97-2003 document"), ("odt", "OpenDocument text"),
             ("rtf", "Rich text"), ("txt", "Plain text"), ("html", "Web page"), ("pages", "Apple Pages"),
             ("wpd", "WordPerfect document"), ("wps", "Works document"), ("docm", "Word macro document"),
             ("dotx", "Word template")]:
    fmt("document", k, name=n, aliases={"html": ["htm", "xhtml"], "txt": ["text"]}.get(k, []))

# Markup (Pandoc)
for k, label, ext, n, al in [
        ("md", "MD", "md", "Markdown", ["markdown", "mdown", "mkd"]),
        ("rst", "RST", "rst", "reStructuredText", []),
        ("tex", "LATEX", "tex", "LaTeX source", ["latex"]),
        ("org", "ORG", "org", "Emacs Org mode", []),
        ("textile", "TEXTILE", "textile", "Textile markup", []),
        ("mediawiki", "WIKI", "wiki", "MediaWiki markup", ["mediawiki"]),
        ("adoc", "ADOC", "adoc", "AsciiDoc", ["asciidoc"]),
        ("ipynb", "IPYNB", "ipynb", "Jupyter notebook", []),
        ("typ", "TYPST", "typ", "Typst source", []),
        ("dbk", "DOCBOOK", "dbk", "DocBook XML", []),
        ("opml", "OPML", "opml", "Outline (OPML)", []),
]:
    fmt("markup", k, label, ext, n, al)

# Spreadsheets
for k, n in [("xlsx", "Excel workbook"), ("xls", "Excel 97-2003 workbook"), ("ods", "OpenDocument spreadsheet"),
             ("csv", "Comma-separated values"), ("tsv", "Tab-separated values"), ("xlsm", "Excel macro workbook"),
             ("numbers", "Apple Numbers")]:
    fmt("spreadsheet", k, name=n, aliases={"tsv": ["tab"]}.get(k, []))

# Presentations
for k, n in [("pptx", "PowerPoint presentation"), ("ppt", "PowerPoint 97-2003"), ("odp", "OpenDocument presentation"),
             ("key", "Apple Keynote"), ("ppsx", "PowerPoint show"), ("pps", "PowerPoint 97 show")]:
    fmt("presentation", k, name=n)

fmt("pdf", "pdf", name="PDF document")

# E-books
for k, n in [("epub", "EPUB e-book"), ("mobi", "Kindle MOBI"), ("azw3", "Kindle AZW3"), ("fb2", "FictionBook"),
             ("lit", "Microsoft Reader"), ("pdb", "Palm e-book"), ("lrf", "Sony Reader"),
             ("htmlz", "Zipped HTML book"), ("txtz", "Zipped text book"), ("snb", "Shanda Bambook"),
             ("tcr", "Psion e-book"), ("cbz", "Comic book archive")]:
    fmt("ebook", k, name=n, aliases={"azw3": ["azw"]}.get(k, []))

# Data
for k, label, ext, n, al in [
        ("json", "JSON", "json", "JSON data", []), ("jsonl", "JSONL", "jsonl", "JSON Lines", ["ndjson"]),
        ("yaml", "YAML", "yaml", "YAML data", ["yml"]), ("xml", "XML", "xml", "XML data", []),
        ("toml", "TOML", "toml", "TOML config", []), ("ini", "INI", "ini", "INI config", ["cfg", "conf"]),
        ("plist", "PLIST", "plist", "Apple property list", []), ("sql", "SQL", "sql", "SQL insert script", []),
        ("mdtable", "MD TABLE", "md", "Markdown table", []), ("htmltable", "HTML TABLE", "html", "HTML table", []),
]:
    fmt("data", k, label, ext, n, al)

# Archives
for k, label, ext, n, al in [
        ("zip", "ZIP", "zip", "ZIP archive", []), ("7z", "7Z", "7z", "7-Zip archive", []),
        ("tar", "TAR", "tar", "Tape archive", []), ("tgz", "TAR.GZ", "tar.gz", "Gzipped tarball", ["tgz", "tar.gz"]),
        ("tbz2", "TAR.BZ2", "tar.bz2", "Bzip2 tarball", ["tbz2", "tbz", "tar.bz2"]),
        ("txz", "TAR.XZ", "tar.xz", "XZ tarball", ["txz", "tar.xz"]), ("rar", "RAR", "rar", "RAR archive", []),
]:
    fmt("archive", k, label, ext, n, al)

# Fonts
for k, n in [("ttf", "TrueType font"), ("otf", "OpenType font"), ("woff", "Web font"), ("woff2", "Web font 2")]:
    fmt("font", k, name=n)

# Subtitles
for k, label, ext, n in [("srt", "SRT", "srt", "SubRip subtitles"), ("vtt", "VTT", "vtt", "WebVTT subtitles"),
                         ("ass", "ASS", "ass", "Advanced SubStation"), ("ssa", "SSA", "ssa", "SubStation Alpha"),
                         ("lrc", "LRC", "lrc", "Lyrics file"), ("ttml", "TTML", "ttml", "Timed Text XML"),
                         ("sbv", "SBV", "sbv", "YouTube subtitles"), ("smi", "SMI", "smi", "SAMI subtitles")]:
    fmt("subtitle", k, label, ext, n)

GROUPS = {
    "video_out": ["mp4", "webm", "mkv", "mov", "avi", "flv", "wmv", "m4v", "mpeg", "3gp", "ogv", "ts"],
    "video_in": ["mp4", "webm", "mkv", "mov", "avi", "flv", "wmv", "m4v", "mpeg", "3gp", "ogv", "ts",
                 "mts", "m2ts", "vob", "f4v", "asf", "mxf", "divx", "rmvb", "dv", "y4m", "hevc"],
    "audio_out": ["mp3", "wav", "flac", "aac", "m4a", "alac", "ogg", "opus", "wma", "aiff", "ac3", "mp2", "caf", "mka", "au"],
    "audio_in": ["mp3", "wav", "flac", "aac", "m4a", "ogg", "opus", "wma", "aiff", "ac3", "mp2", "caf", "mka", "au",
                 "amr", "ape", "wv", "dts", "tta", "voc"],
    "raster": ["png", "jpg", "webp", "avif", "heic", "gif", "bmp", "tiff", "ico", "icns", "tga", "jp2", "ppm",
               "pcx", "dds", "psd", "qoi"],
}

# --------------------------------------------------------------------------
# Options (rendered automatically by the website)
# --------------------------------------------------------------------------

def _sel(label, choices, default, hint=""):
    return {"type": "select", "label": label, "choices": choices, "default": default, "hint": hint}


OPTIONS = {
    # video
    "resolution": _sel("Resolution", [["keep", "Original"], ["2160", "4K"], ["1440", "1440p"], ["1080", "1080p"],
                                      ["720", "720p"], ["480", "480p"], ["360", "360p"], ["240", "240p"]], "keep",
                       "Never upscales."),
    "vquality": _sel("Quality", [["best", "Best"], ["high", "High"], ["balanced", "Balanced"], ["small", "Smallest"]],
                     "high"),
    "vcodec": _sel("Codec", [["h264", "H.264"], ["h265", "H.265"], ["av1", "AV1"]], "h264",
                   "H.264 plays everywhere. H.265 is about half the size. AV1 is smallest but slow."),
    "fps": _sel("Frame rate", [["keep", "Original"], ["60", "60"], ["30", "30"], ["24", "24"], ["15", "15"]], "keep"),
    "mute": {"type": "toggle", "label": "Remove audio", "default": False},
    # audio
    "abitrate": _sel("Bitrate", [["64", "64 kbps"], ["96", "96 kbps"], ["128", "128 kbps"], ["160", "160 kbps"],
                                 ["192", "192 kbps"], ["256", "256 kbps"], ["320", "320 kbps"]], "192"),
    "samplerate": _sel("Sample rate", [["keep", "Original"], ["48000", "48 kHz"], ["44100", "44.1 kHz"],
                                       ["32000", "32 kHz"], ["22050", "22 kHz"]], "keep"),
    "channels": _sel("Channels", [["keep", "Original"], ["2", "Stereo"], ["1", "Mono"]], "keep"),
    "volume": {"type": "range", "label": "Volume", "min": 0, "max": 200, "step": 5, "default": 100, "unit": "%"},
    "normalize": {"type": "toggle", "label": "Even out loudness", "default": False},
    # timing
    "trim_start": {"type": "time", "label": "Start at", "placeholder": "0:00", "default": ""},
    "trim_end": {"type": "time", "label": "End at", "placeholder": "end", "default": ""},
    # gif / animated
    "gif_fps": _sel("Frame rate", [["8", "8"], ["10", "10"], ["15", "15"], ["20", "20"], ["25", "25"]], "15"),
    "gif_width": _sel("Width", [["keep", "Original"], ["720", "720 px"], ["480", "480 px"], ["360", "360 px"],
                                ["240", "240 px"]], "480"),
    # images
    "quality": {"type": "range", "label": "Quality", "min": 10, "max": 100, "step": 1, "default": 88, "unit": ""},
    "width": {"type": "number", "label": "Width", "placeholder": "auto", "default": "", "min": 1, "max": 20000, "unit": "px"},
    "height": {"type": "number", "label": "Height", "placeholder": "auto", "default": "", "min": 1, "max": 20000, "unit": "px"},
    "rotate": _sel("Rotate", [["0", "None"], ["90", "90° right"], ["180", "180°"], ["270", "90° left"]], "0"),
    "flip": _sel("Flip", [["none", "None"], ["h", "Horizontal"], ["v", "Vertical"]], "none"),
    "grayscale": {"type": "toggle", "label": "Black & white", "default": False},
    "keep_meta": {"type": "toggle", "label": "Keep photo metadata (EXIF)", "default": False},
    "background": {"type": "color", "label": "Fill transparency with", "default": "#ffffff"},
    # pdf
    "dpi": _sel("Sharpness", [["72", "72 dpi"], ["150", "150 dpi"], ["300", "300 dpi"]], "150",
                "72 for screens, 300 for printing."),
    "pages": {"type": "text", "label": "Pages", "placeholder": "all  (e.g. 1-3, 7)", "default": ""},
    # ocr
    "ocr_lang": _sel("Language", [["eng", "English"], ["spa", "Spanish"], ["fra", "French"], ["deu", "German"],
                                  ["ita", "Italian"], ["por", "Portuguese"], ["hin", "Hindi"], ["chi_sim", "Chinese"],
                                  ["jpn", "Japanese"]], "eng", "Other languages need the matching Tesseract pack."),
    # data
    "indent": _sel("Formatting", [["2", "Pretty (2 spaces)"], ["4", "Pretty (4 spaces)"], ["0", "Compact"]], "2"),
    "infer": {"type": "toggle", "label": "Detect numbers & true/false", "default": True},
    "sheet": {"type": "text", "label": "Sheet", "placeholder": "first sheet", "default": ""},
    # archives
    "level": _sel("Compression", [["fast", "Fast"], ["normal", "Normal"], ["max", "Maximum"]], "normal"),
}


def clean_options(ids, raw: dict):
    """Validate user-supplied options, falling back to defaults."""
    out = {}
    for oid in ids:
        spec = OPTIONS[oid]
        val = raw.get(oid, spec.get("default"))
        t = spec["type"]
        if t == "select":
            allowed = [c[0] for c in spec["choices"]]
            val = str(val) if str(val) in allowed else spec["default"]
        elif t == "toggle":
            val = val in (True, "true", "1", 1, "on")
        elif t == "range":
            try:
                val = max(spec["min"], min(spec["max"], float(val)))
            except (TypeError, ValueError):
                val = spec["default"]
        elif t == "number":
            try:
                val = int(float(val)) if str(val).strip() else None
                if val is not None:
                    val = max(spec["min"], min(spec["max"], val))
            except (TypeError, ValueError):
                val = None
        elif t == "time":
            val = parse_time(val)
        elif t == "color":
            val = val if isinstance(val, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", val) else spec["default"]
        else:  # text
            val = str(val or "").strip()[:200]
        out[oid] = val
    return out


def parse_time(value):
    """'1:05' -> 65.0, '90' -> 90.0, '1:02:03.5' -> 3723.5; blank/invalid -> None."""
    s = str(value or "").strip()
    if not s:
        return None
    if not re.fullmatch(r"\d+(?::\d{1,2}){0,2}(?:\.\d+)?", s):
        return None
    parts = [float(p) for p in s.split(":")]
    seconds = 0.0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@dataclass
class Route:
    src: str
    dst: str
    fn: Callable
    options: tuple
    requires: tuple
    priority: int
    engine: str


_CANDIDATES: list[Route] = []
ROUTES: dict[tuple[str, str], Route] = {}
LOCKED: dict[str, set] = {}  # requirement -> {(src, dst), ...} that installing it would unlock


def converter(srcs, dsts, *, options=(), requires=(), priority=0, engine="", same=False):
    """same=True also offers X → X (useful to shrink, trim or resize without changing format)."""
    def deco(fn):
        for s in srcs:
            for d in dsts:
                if s == d and not same:
                    continue
                opts = options(s, d) if callable(options) else tuple(options)
                _CANDIDATES.append(Route(s, d, fn, tuple(opts), tuple(requires), priority, engine))
        return fn
    return deco


def build():
    ROUTES.clear()
    LOCKED.clear()
    blocked = []
    for r in _CANDIDATES:
        missing = [req for req in r.requires if not tools.available(req)]
        if missing:
            blocked.append((r, missing))
            continue
        cur = ROUTES.get((r.src, r.dst))
        if cur is None or r.priority > cur.priority:
            ROUTES[(r.src, r.dst)] = r
    for r, missing in blocked:
        if (r.src, r.dst) in ROUTES:
            continue
        for req in missing:
            if req.startswith(("enc:", "pil:", "pilsave:", "pandoc-r:", "pandoc-w:")):
                continue  # not something a person can fix with one install
            LOCKED.setdefault(req, set()).add((r.src, r.dst))


def catalogue():
    """Everything the website needs, in one compact JSON-friendly dict."""
    option_sets, set_index = [], {}
    routes = {}
    for (s, d), r in sorted(ROUTES.items()):
        key = r.options
        if key not in set_index:
            set_index[key] = len(option_sets)
            option_sets.append(list(key))
        routes.setdefault(s, []).append([d, set_index[key]])
    used = {s for s in routes} | {d for (_, d) in ROUTES}
    locked = []
    for req, pairs in sorted(LOCKED.items(), key=lambda kv: -len(kv[1])):
        label, what, how = tools.INSTALL_HINTS.get(req, (req, "", ""))
        sample = sorted(pairs)[:4]
        locked.append({"tool": label, "what": what, "how": how, "count": len(pairs),
                       "examples": [f"{FORMATS[s].label} → {FORMATS[d].label}" for s, d in sample]})
    return {
        "categories": [{"id": c, "label": l} for c, l in CATEGORIES],
        "formats": {k: {"label": f.label, "category": f.category, "ext": f.ext, "name": f.name}
                    for k, f in FORMATS.items() if k in used},
        "routes": routes,
        "option_sets": option_sets,
        "options": OPTIONS,
        "locked": locked,
        "aliases": {e: k for e, k in _EXT_TO_KEY.items() if k in used},
        "total_routes": len(ROUTES),
    }


# --------------------------------------------------------------------------
# What a converter function receives
# --------------------------------------------------------------------------

class Cancelled(Exception):
    pass


class ConversionError(Exception):
    """An error with a message that is safe and friendly to show to people."""


@dataclass
class Context:
    src: Path                 # the uploaded file
    src_fmt: str              # e.g. "mov"
    dst_fmt: str              # e.g. "mp4"
    work: Path                # a private scratch folder for this job
    opts: dict = field(default_factory=dict)
    stem: str = "file"        # original file name without extension
    job: object = None        # set by the job runner (progress + cancel)

    @property
    def dst(self) -> Format:
        return FORMATS[self.dst_fmt]

    def out(self, key=None, suffix=""):
        """Path for an output file named after the original upload."""
        f = FORMATS[key or self.dst_fmt]
        out_dir = self.work / "out"
        out_dir.mkdir(exist_ok=True)
        return out_dir / f"{self.stem}{suffix}.{f.ext}"

    def tmp(self, name):
        d = self.work / "tmp"
        d.mkdir(exist_ok=True)
        return d / name

    def progress(self, fraction=None, message=None):
        if self.job:
            self.job.update(fraction, message)

    def check_cancel(self):
        if self.job and self.job.cancelled:
            raise Cancelled()
