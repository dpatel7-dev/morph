"""Image conversions (Pillow), SVG rendering, and image-to-text OCR."""
import subprocess

from core import tools
from core.registry import GROUPS, ConversionError, converter
from core.util import CREATE_NO_WINDOW, run

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
    Image.MAX_IMAGE_PIXELS = 400_000_000  # allow big photos, still guard against decompression bombs
except ImportError:  # Pillow is in requirements.txt, but fail softly
    Image = None

# Pillow's name for each output, plus anything extra it needs
SAVE_AS = {
    "png": "PNG", "jpg": "JPEG", "webp": "WEBP", "avif": "AVIF", "heic": "HEIF", "gif": "GIF", "bmp": "BMP",
    "tiff": "TIFF", "ico": "ICO", "icns": "ICNS", "tga": "TGA", "jp2": "JPEG2000", "ppm": "PPM", "pcx": "PCX",
    "dds": "DDS", "qoi": "QOI", "pdf": "PDF",
}
NEEDS = {  # requirements for reading/writing particular formats
    "avif": ["pil:avif"], "heic": ["heif"], "jp2": ["pil:jpg_2000"], "svg": ["svg"],
    "qoi": ["pilsave:QOI"], "dds": ["pilsave:DDS"],
}
READ_ONLY = {"psd"}
LOSSY = {"jpg", "webp", "avif", "heic", "jp2"}
NO_ALPHA = {"jpg", "bmp", "ppm", "pcx", "pdf"}
META = {"jpg", "webp", "png", "tiff", "avif", "heic"}
ICONS = {"ico", "icns"}
ANIMATED_OUT = {"gif", "webp", "png", "avif"}


def image_options(src, dst):
    opts = []
    if dst in LOSSY:
        opts.append("quality")
    if dst not in ICONS:
        opts += ["width", "height"]
    opts += ["rotate", "flip", "grayscale"]
    if dst in NO_ALPHA:
        opts.append("background")
    if dst in META:
        opts.append("keep_meta")
    return opts


# --------------------------------------------------------------------------
# Opening
# --------------------------------------------------------------------------

def render_svg(ctx, out_path, fmt="png", width=None, height=None):
    r = tools.svg_renderer()
    if r == "rsvg":
        cmd = [tools.rsvg(), "-f", fmt, "-o", out_path]
        if width:
            cmd += ["-w", width]
        if height:
            cmd += ["-h", height]
        run(cmd + [ctx.src], ctx, friendly="Couldn't draw this SVG.")
    elif r == "cairosvg":
        import cairosvg
        fn = {"png": cairosvg.svg2png, "pdf": cairosvg.svg2pdf}[fmt]
        try:
            fn(url=str(ctx.src), write_to=str(out_path), output_width=width, output_height=height)
        except Exception as e:
            raise ConversionError(f"Couldn't draw this SVG: {e}")
    elif r == "magick":
        cmd = [tools.magick(), "-background", "none", "-density", "192", ctx.src]
        if width or height:
            cmd += ["-resize", f"{width or ''}x{height or ''}" + ("!" if width and height else "")]
        run(cmd + [f"{fmt}:{out_path}"], ctx, friendly="Couldn't draw this SVG.")
    else:
        raise ConversionError("No SVG renderer is installed.")
    return out_path


def open_image(ctx):
    if Image is None:
        raise ConversionError("Pillow isn't installed (pip install pillow).")
    if ctx.src_fmt == "heic":
        tools.heif_ok()
    path = ctx.src
    if ctx.src_fmt == "svg":
        w, h = ctx.opts.get("width"), ctx.opts.get("height")
        path = render_svg(ctx, ctx.tmp("render.png"), "png", w, h)
    try:
        img = Image.open(path)
        img.load()
    except UnidentifiedImageError:
        raise ConversionError("This image couldn't be opened. It may be damaged or not really a "
                              f"{ctx.src_fmt.upper()} file.")
    except Image.DecompressionBombError:
        raise ConversionError("This image is enormous (over 400 megapixels), so it was skipped for safety.")
    return img


# --------------------------------------------------------------------------
# Editing
# --------------------------------------------------------------------------

def has_alpha(img):
    return img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)


def flatten(img, color="#ffffff"):
    """Put transparent pixels on a solid colour (for formats without transparency)."""
    if has_alpha(img):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, color)
        bg.alpha_composite(rgba)
        return bg.convert("RGB")
    if img.mode not in ("RGB", "L"):
        return img.convert("RGB")
    return img


def transform(img, opts, dst, skip_resize=False):
    rot = int(opts.get("rotate") or 0)
    if rot:
        img = img.rotate(-rot, expand=True)
    flip = opts.get("flip", "none")
    if flip == "h":
        img = ImageOps.mirror(img)
    elif flip == "v":
        img = ImageOps.flip(img)
    if opts.get("grayscale"):
        img = img.convert("LA" if has_alpha(img) else "L")
    if not skip_resize:
        w, h = opts.get("width"), opts.get("height")
        if w or h:
            ow, oh = img.size
            if w and h:
                size = (w, h)
            elif w:
                size = (w, max(1, round(oh * w / ow)))
            else:
                size = (max(1, round(ow * h / oh)), h)
            if img.mode == "P":
                img = img.convert("RGBA")
            img = img.resize(size, Image.LANCZOS)
    return img


def square(img):
    """Pad to a square canvas (icons must be square)."""
    img = img.convert("RGBA")
    w, h = img.size
    if w == h:
        return img
    s = max(w, h)
    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    canvas.paste(img, ((s - w) // 2, (s - h) // 2))
    return canvas


def gif_frame(img):
    """Convert one RGBA image into a palette image that keeps transparency."""
    if not has_alpha(img):
        return img.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=256)
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    p = rgba.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
    mask = alpha.point(lambda a: 255 if a <= 128 else 0)
    p.paste(255, mask)
    p.info["transparency"] = 255
    return p


# --------------------------------------------------------------------------
# Saving
# --------------------------------------------------------------------------

def save(img, out, dst, opts, exif=None, icc=None):
    q = int(opts.get("quality") or 88)
    bg = opts.get("background") or "#ffffff"
    kw = {}
    if icc:
        kw["icc_profile"] = icc
    if exif and dst in META:
        kw["exif"] = exif

    if dst == "jpg":
        img = flatten(img, bg)
        img.save(out, "JPEG", quality=q, optimize=True, progressive=True,
                 subsampling=0 if q >= 90 else 2, **kw)
    elif dst == "png":
        if img.mode not in ("1", "L", "LA", "P", "RGB", "RGBA", "I", "I;16"):
            img = img.convert("RGBA" if has_alpha(img) else "RGB")
        img.save(out, "PNG", optimize=img.width * img.height < 16_000_000, **kw)
    elif dst in ("webp", "avif", "heic"):
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if has_alpha(img) else "RGB")
        if dst == "webp":
            img.save(out, "WEBP", quality=q, method=4, lossless=q >= 100, **kw)
        elif dst == "avif":
            img.save(out, "AVIF", quality=q, **kw)
        else:
            img.save(out, "HEIF", quality=-1 if q >= 100 else q, **kw)
    elif dst == "gif":
        gif_frame(img).save(out, "GIF", optimize=True)
    elif dst == "bmp":
        flatten(img, bg).save(out, "BMP")
    elif dst == "tiff":
        if img.mode == "P":
            img = img.convert("RGBA" if has_alpha(img) else "RGB")
        img.save(out, "TIFF", compression="tiff_lzw", **kw)
    elif dst == "ico":
        sq = square(img)
        if 64 <= sq.size[0] < 256:
            sq = sq.resize((256, 256), Image.LANCZOS)
        sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= sq.size[0]] or [sq.size]
        sq.save(out, "ICO", sizes=sizes)
    elif dst == "icns":
        sq = square(img)
        if sq.size[0] < 512:
            sq = sq.resize((512, 512), Image.LANCZOS)
        sq.save(out, "ICNS")
    elif dst == "tga":
        img.convert("RGBA" if has_alpha(img) else "RGB").save(out, "TGA", compression="tga_rle")
    elif dst == "jp2":
        img = img.convert("RGBA" if has_alpha(img) else "RGB")
        if q >= 100:
            img.save(out, "JPEG2000", irreversible=False)
        else:
            img.save(out, "JPEG2000", quality_mode="dB", quality_layers=[round(22 + q * 0.28, 1)], irreversible=True)
    elif dst == "ppm":
        img = flatten(img, bg)
        img.save(out, "PPM")
    elif dst == "pcx":
        flatten(img, bg).save(out, "PCX")
    elif dst == "dds":
        img.convert("RGBA").save(out, "DDS")
    elif dst == "qoi":
        img.convert("RGBA" if has_alpha(img) else "RGB").save(out, "QOI")
    elif dst == "pdf":
        dpi = img.info.get("dpi", (72, 72))[0] or 72
        flatten(img, bg).save(out, "PDF", resolution=float(dpi))
    else:
        raise ConversionError(f"Saving as {dst.upper()} isn't supported.")


def convert_image(ctx):
    dst = ctx.dst_fmt
    opts = ctx.opts

    # SVG -> PDF stays crisp (vector) when the renderer supports it
    if ctx.src_fmt == "svg" and dst == "pdf" and tools.svg_renderer() in ("rsvg", "cairosvg") \
            and not any(opts.get(k) for k in ("rotate", "grayscale")) and opts.get("flip", "none") == "none":
        out = ctx.out()
        render_svg(ctx, out, "pdf", opts.get("width"), opts.get("height"))
        return out

    ctx.progress(None, "Reading image…")
    img = open_image(ctx)
    icc = img.info.get("icc_profile")
    out = ctx.out()
    n_frames = getattr(img, "n_frames", 1)

    # Animated in -> animated out (GIF, WebP, APNG, AVIF)
    if n_frames > 1 and getattr(img, "is_animated", False) and dst in ANIMATED_OUT:
        frames, durations = [], []
        loop = img.info.get("loop", 0)
        for i in range(n_frames):
            ctx.check_cancel()
            img.seek(i)
            durations.append(img.info.get("duration", 100) or 100)
            f = transform(img.convert("RGBA"), opts, dst)
            frames.append(gif_frame(f) if dst == "gif" else f)
            ctx.progress((i + 1) / n_frames * 0.8, f"Frame {i + 1} of {n_frames}…")
        extra = {"disposal": 2, "optimize": False} if dst == "gif" else {}
        if dst in ("webp", "avif"):
            extra["quality"] = int(opts.get("quality") or 88)
        ctx.progress(0.9, "Saving animation…")
        frames[0].save(out, {"gif": "GIF", "webp": "WEBP", "png": "PNG", "avif": "AVIF"}[dst],
                       save_all=True, append_images=frames[1:], duration=durations, loop=loop, **extra)
        return out

    # Multi-page TIFF -> multi-page PDF / TIFF
    if n_frames > 1 and dst in ("pdf", "tiff") and ctx.src_fmt in ("tiff", "gif"):
        pages = []
        for i in range(n_frames):
            img.seek(i)
            p = transform(img.copy(), opts, dst)
            pages.append(flatten(p, opts.get("background") or "#ffffff") if dst == "pdf" else p.convert("RGB"))
        pages[0].save(out, "PDF" if dst == "pdf" else "TIFF", save_all=True, append_images=pages[1:])
        return out

    exif = None
    if ctx.src_fmt != "svg":
        img = ImageOps.exif_transpose(img) or img
        if opts.get("keep_meta"):
            try:
                exif = img.getexif().tobytes() or None
            except Exception:
                exif = None
    img = transform(img, opts, dst, skip_resize=ctx.src_fmt == "svg")
    ctx.progress(0.7, "Saving…")
    save(img, out, dst, opts, exif=exif, icc=icc)
    return out


IMAGE_IN = GROUPS["raster"] + ["svg"]
IMAGE_OUT = [f for f in GROUPS["raster"] if f not in READ_ONLY] + ["pdf"]

for _s in IMAGE_IN:
    for _d in IMAGE_OUT:
        reqs = ["py:PIL"] + NEEDS.get(_s, []) + NEEDS.get(_d, [])
        # SVG -> PDF is usually best done as vectors: give it a priority bump
        converter([_s], [_d], options=image_options, requires=reqs, engine="Pillow", same=True,
                  priority=1 if (_s, _d) == ("svg", "pdf") else 0)(convert_image)


# --------------------------------------------------------------------------
# OCR: picture of text -> text
# --------------------------------------------------------------------------

@converter(["png", "jpg", "webp", "bmp", "tiff", "gif", "heic", "avif", "jp2", "ppm"], ["txt"],
           options=["ocr_lang"], requires=["tesseract", "py:PIL"], engine="Tesseract OCR")
def ocr(ctx):
    ctx.progress(None, "Reading text from the image…")
    img = open_image(ctx)
    img = ImageOps.exif_transpose(img) or img
    clean = ctx.tmp("ocr.png")
    flatten(img).save(clean, "PNG")
    lang = ctx.opts.get("ocr_lang", "eng")
    base = ctx.tmp("ocr-result")
    try:
        langs = subprocess.run([tools.tesseract(), "--list-langs"], capture_output=True, text=True,
                               timeout=30, creationflags=CREATE_NO_WINDOW).stdout.split()
    except Exception:
        langs = []
    if langs and lang not in langs:
        raise ConversionError(f"The Tesseract language pack “{lang}” isn't installed.")
    run([tools.tesseract(), clean, base, "-l", lang], ctx, friendly="Text recognition failed.")
    result = base.with_suffix(".txt")
    text = result.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        raise ConversionError("I couldn't find any readable text in this image.")
    out = ctx.out()
    out.write_text(text + "\n", encoding="utf-8")
    return out
