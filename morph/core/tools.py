"""
Finds the helper programs Morph uses (FFmpeg, LibreOffice, Pandoc, ...).

Nothing here is required except Python itself: every conversion declares what
it needs, and conversions whose helpers are missing are simply hidden in the
website (with a hint about what to install to unlock them).
"""
import functools
import importlib.util
import os
import platform
import re
import shutil
import subprocess

IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"


def _which(*names):
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def _first_existing(*paths):
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return None


def has_module(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


# --------------------------------------------------------------------------
# Individual tools
# --------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def ffmpeg():
    """FFmpeg: a real install on PATH, or the copy bundled by `pip install imageio-ffmpeg`."""
    path = os.environ.get("MORPH_FFMPEG") or _which("ffmpeg")
    if path:
        return path
    if has_module("imageio_ffmpeg"):
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None
    return None


@functools.lru_cache(maxsize=None)
def ffmpeg_encoders():
    exe = ffmpeg()
    if not exe:
        return set()
    try:
        out = subprocess.run([exe, "-hide_banner", "-encoders"], capture_output=True,
                             text=True, timeout=20).stdout
    except Exception:
        return set()
    names = set()
    for line in out.splitlines():
        m = re.match(r"^\s*[VAS][\.FSXBD]{5}\s+(\S+)", line)
        if m:
            names.add(m.group(1))
    return names


@functools.lru_cache(maxsize=None)
def soffice():
    """LibreOffice (handles Word, Excel, PowerPoint and friends)."""
    path = (os.environ.get("MORPH_SOFFICE")
            or _which("soffice", "libreoffice")
            or _first_existing(
                r"C:\Program Files\LibreOffice\program\soffice.exe",
                r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            ))
    # On Windows, soffice.com waits for the conversion to finish; soffice.exe may not
    if path and IS_WINDOWS and path.lower().endswith("soffice.exe"):
        com = path[:-4] + ".com"
        if os.path.isfile(com):
            return com
    return path


@functools.lru_cache(maxsize=None)
def pandoc():
    """Pandoc: a real install, or the copy bundled by `pip install pypandoc_binary`."""
    path = os.environ.get("MORPH_PANDOC") or _which("pandoc")
    if path:
        return path
    if has_module("pypandoc"):
        try:
            import pypandoc
            return pypandoc.get_pandoc_path()
        except Exception:
            return None
    return None


@functools.lru_cache(maxsize=None)
def pandoc_formats():
    exe = pandoc()
    if not exe:
        return set(), set()
    try:
        r = subprocess.run([exe, "--list-input-formats"], capture_output=True, text=True, timeout=20)
        w = subprocess.run([exe, "--list-output-formats"], capture_output=True, text=True, timeout=20)
        return set(r.stdout.split()), set(w.stdout.split())
    except Exception:
        return set(), set()


@functools.lru_cache(maxsize=None)
def pandoc_version():
    exe = pandoc()
    if not exe:
        return (0,)
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20).stdout
        m = re.search(r"pandoc(?:\.exe)?\s+([\d.]+)", out)
        return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)
    except Exception:
        return (0,)


@functools.lru_cache(maxsize=None)
def calibre():
    return (_which("ebook-convert")
            or _first_existing(
                r"C:\Program Files\Calibre2\ebook-convert.exe",
                r"C:\Program Files\Calibre\ebook-convert.exe",
                "/Applications/calibre.app/Contents/MacOS/ebook-convert",
            ))


@functools.lru_cache(maxsize=None)
def tesseract():
    return (_which("tesseract")
            or _first_existing(r"C:\Program Files\Tesseract-OCR\tesseract.exe"))


@functools.lru_cache(maxsize=None)
def sevenzip():
    return (_which("7z", "7zz", "7za")
            or _first_existing(r"C:\Program Files\7-Zip\7z.exe"))


@functools.lru_cache(maxsize=None)
def rsvg():
    return _which("rsvg-convert")


@functools.lru_cache(maxsize=None)
def magick():
    # On Windows "convert.exe" is a built-in disk tool, so only trust "magick" there.
    if IS_WINDOWS:
        return _which("magick")
    return _which("magick", "convert")


@functools.lru_cache(maxsize=None)
def pdftotext():
    return _which("pdftotext")


@functools.lru_cache(maxsize=None)
def js_runtimes():
    """JavaScript runtimes yt-dlp can use to solve YouTube's player challenges."""
    found = {}
    for name in ("deno", "node", "bun"):
        p = _which(name)
        if not p and name == "deno":
            home_deno = os.path.join(os.path.expanduser("~"), ".deno", "bin",
                                     "deno.exe" if IS_WINDOWS else "deno")
            p = _first_existing(home_deno)
        if p:
            found[name] = p
    return found


@functools.lru_cache(maxsize=None)
def pil_feature(name):
    try:
        from PIL import features
        return bool(features.check(name))
    except Exception:
        return False


@functools.lru_cache(maxsize=None)
def pil_can_save(fmt_name):
    try:
        from PIL import Image
        Image.init()
        return fmt_name.upper() in Image.SAVE
    except Exception:
        return False


@functools.lru_cache(maxsize=None)
def heif_ok():
    if not has_module("pillow_heif"):
        return False
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        return True
    except Exception:
        return False


@functools.lru_cache(maxsize=None)
def svg_renderer():
    if rsvg():
        return "rsvg"
    if has_module("cairosvg"):
        try:
            import cairosvg  # noqa: F401  (needs the cairo C library)
            return "cairosvg"
        except Exception:
            pass
    if magick():
        return "magick"
    return None


# --------------------------------------------------------------------------
# Requirement strings used by converters
# --------------------------------------------------------------------------

def available(req):
    """Is a requirement such as 'ffmpeg', 'enc:libx265' or 'py:pypdf' satisfied?"""
    if req.startswith("py:"):
        return has_module(req[3:])
    if req.startswith("enc:"):
        return req[4:] in ffmpeg_encoders()
    if req.startswith("pil:"):
        return pil_feature(req[4:])
    if req.startswith("pilsave:"):
        return pil_can_save(req[8:])
    if req.startswith("pandoc-r:"):
        return req[9:] in pandoc_formats()[0]
    if req.startswith("pandoc-w:"):
        return req[9:] in pandoc_formats()[1]
    simple = {
        "ffmpeg": ffmpeg, "soffice": soffice, "pandoc": pandoc, "calibre": calibre,
        "tesseract": tesseract, "7z": sevenzip, "svg": svg_renderer, "heif": heif_ok,
        "pdf2docx": lambda: has_module("pdf2docx"),
        "7zany": lambda: has_module("py7zr") or bool(sevenzip()),
    }
    fn = simple.get(req)
    return bool(fn and fn())


# What to tell people when something is missing.
INSTALL_HINTS = {
    "ffmpeg": ("FFmpeg", "audio & video", "pip install imageio-ffmpeg  (or install FFmpeg from ffmpeg.org)"),
    "soffice": ("LibreOffice", "Word, Excel & PowerPoint files", "Install LibreOffice from libreoffice.org"),
    "pandoc": ("Pandoc", "Markdown, LaTeX, EPUB & more", "pip install pypandoc_binary  (or install from pandoc.org)"),
    "calibre": ("Calibre", "Kindle & e-book formats", "Install Calibre from calibre-ebook.com"),
    "tesseract": ("Tesseract", "text recognition (OCR)", "Install Tesseract OCR"),
    "7z": ("7-Zip", "RAR archives", "Install 7-Zip from 7-zip.org"),
    "7zany": ("py7zr", "7Z archives", "pip install py7zr  (or install 7-Zip)"),
    "svg": ("ImageMagick", "SVG images", "Install ImageMagick from imagemagick.org"),
    "heif": ("pillow-heif", "iPhone HEIC photos", "pip install pillow-heif"),
    "py:pypdf": ("pypdf", "PDF tools", "pip install pypdf"),
    "py:pypdfium2": ("pypdfium2", "PDF to image", "pip install pypdfium2"),
    "py:openpyxl": ("openpyxl", "Excel without LibreOffice", "pip install openpyxl"),
    "py:yaml": ("PyYAML", "YAML files", "pip install pyyaml"),
    "py:fontTools": ("fontTools", "font files", "pip install fonttools"),
    "py:brotli": ("brotli", "WOFF2 fonts", "pip install brotli"),
    "py:py7zr": ("py7zr", "7Z archives", "pip install py7zr"),
}


def describe():
    """A small status report for the website's 'Engine room' panel."""
    return {
        "ffmpeg": bool(ffmpeg()),
        "libreoffice": bool(soffice()),
        "pandoc": bool(pandoc()),
        "calibre": bool(calibre()),
        "tesseract": bool(tesseract()),
        "sevenzip": bool(sevenzip()),
        "svg": bool(svg_renderer()),
        "heic": heif_ok(),
        "ytdlp": has_module("yt_dlp"),
        "js_runtime": sorted(js_runtimes().keys()),
    }
