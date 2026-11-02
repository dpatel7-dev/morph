"""PDF to images/text/Word, plus the PDF tools (merge, split, compress, rotate, images → PDF)."""
import io
import shutil
import zipfile

from core import tools
from core.registry import FORMATS, ConversionError, converter, detect_format
from core.util import one_or_zip, parse_pages, run, zip_files


def _open_pdfium(path):
    import pypdfium2 as pdfium
    try:
        return pdfium.PdfDocument(str(path))
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg:
            raise ConversionError("This PDF is password-protected. Unlock it first, then try again.")
        raise ConversionError("This PDF couldn't be opened. It may be damaged.")


def render_pdf(ctx, path, label="pages"):
    """Render PDF pages to images (used for PDF → PNG/JPG and slides → images)."""
    from PIL import Image  # noqa: F401
    from converters.images import flatten
    pdf = _open_pdfium(path)
    try:
        pages = parse_pages(ctx.opts.get("pages", ""), len(pdf))
        dpi = int(ctx.opts.get("dpi") or 150)
        dst = ctx.dst_fmt
        rendered = []
        for n, i in enumerate(pages, 1):
            ctx.check_cancel()
            ctx.progress((n - 1) / len(pages), f"Rendering page {n} of {len(pages)}…")
            img = pdf[i].render(scale=dpi / 72).to_pil()
            if dst == "tiff":
                rendered.append(img.convert("RGB"))
                continue
            out = ctx.work / "out" / f"{ctx.stem}-{label[:-1] if label.endswith('s') else label}-{i + 1:03}.{FORMATS[dst].ext}"
            out.parent.mkdir(exist_ok=True)
            if dst == "jpg":
                flatten(img).save(out, "JPEG", quality=90, optimize=True, dpi=(dpi, dpi))
            elif dst == "webp":
                img.save(out, "WEBP", quality=88)
            elif dst == "bmp":
                flatten(img).save(out, "BMP")
            else:
                img.save(out, "PNG", optimize=True, dpi=(dpi, dpi))
            rendered.append(out)
        if dst == "tiff":
            out = ctx.out()
            rendered[0].save(out, "TIFF", save_all=True, append_images=rendered[1:], compression="tiff_lzw",
                             dpi=(dpi, dpi))
            return out
        return one_or_zip(rendered, ctx, label)
    finally:
        pdf.close()


@converter(["pdf"], ["png", "jpg", "webp", "tiff", "bmp"], options=["dpi", "pages"],
           requires=["py:pypdfium2", "py:PIL"], engine="PDFium")
def pdf_to_images(ctx):
    return render_pdf(ctx, ctx.src)


@converter(["pdf"], ["txt"], options=["pages"], requires=["py:pypdf"], engine="pypdf")
def pdf_to_text(ctx):
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(ctx.src))
        if reader.is_encrypted:
            reader.decrypt("")
        n = len(reader.pages)
    except Exception:
        raise ConversionError("This PDF couldn't be opened. It may be damaged or password-protected.")
    pages = parse_pages(ctx.opts.get("pages", ""), n)
    out = ctx.out()
    if tools.pdftotext():
        first, last = min(pages) + 1, max(pages) + 1
        run([tools.pdftotext(), "-layout", "-enc", "UTF-8", "-f", first, "-l", last, ctx.src, out], ctx,
            friendly="Couldn't read text from this PDF.")
        text = out.read_text(encoding="utf-8", errors="replace")
    else:
        chunks = []
        for k, i in enumerate(pages, 1):
            ctx.progress(k / len(pages), f"Reading page {k} of {len(pages)}…")
            chunks.append(reader.pages[i].extract_text() or "")
        text = "\n\n\f".join(chunks)
        out.write_text(text, encoding="utf-8")
    if not text.strip():
        raise ConversionError("This PDF has no selectable text (it's probably scanned images). "
                              "Convert it to PNG first, then use PNG → TXT to read the text.")
    return out


@converter(["pdf"], ["docx"], requires=["pdf2docx"], priority=5, engine="pdf2docx")
def pdf_to_docx(ctx):
    from pdf2docx import Converter
    out = ctx.out()
    ctx.progress(None, "Rebuilding the layout in Word…")
    cv = Converter(str(ctx.src))
    try:
        cv.convert(str(out))
    except Exception as e:
        raise ConversionError(f"Couldn't rebuild this PDF as a Word file: {e}")
    finally:
        cv.close()
    return out


@converter(["cbz"], ["pdf"], requires=["py:PIL"], priority=1, engine="Pillow")
def comic_to_pdf(ctx):
    from PIL import Image
    from converters.images import flatten
    pages = []
    with zipfile.ZipFile(ctx.src) as z:
        names = sorted(n for n in z.namelist()
                       if detect_format(n) in ("jpg", "png", "webp", "gif", "bmp") and not n.startswith("__MACOSX"))
        if not names:
            raise ConversionError("This comic archive has no pictures in it.")
        for k, name in enumerate(names, 1):
            ctx.progress(k / len(names) * 0.8, f"Adding page {k} of {len(names)}…")
            with z.open(name) as f:
                pages.append(flatten(Image.open(io.BytesIO(f.read()))))
    out = ctx.out()
    pages[0].save(out, "PDF", save_all=True, append_images=pages[1:], resolution=150.0)
    return out


# --------------------------------------------------------------------------
# Tools that take several files (called from app.py)
# --------------------------------------------------------------------------

TOOLS = {
    "merge-pdf": {"title": "Merge PDFs", "accept": ["pdf"], "multi": True,
                  "blurb": "Stack several PDFs into one, in the order shown."},
    "split-pdf": {"title": "Split PDF", "accept": ["pdf"], "multi": False,
                  "blurb": "One file per page, or your own page ranges.",
                  "options": {"ranges": {"type": "text", "label": "Ranges",
                                         "placeholder": "every page  (or 1-3, 4-9)", "default": ""}}},
    "compress-pdf": {"title": "Compress PDF", "accept": ["pdf"], "multi": False,
                     "blurb": "Shrink photos inside a PDF so it's easier to email.",
                     "options": {"strength": {"type": "select", "label": "Strength", "default": "balanced",
                                              "choices": [["light", "Light"], ["balanced", "Balanced"],
                                                          ["strong", "Strong"]]}}},
    "rotate-pdf": {"title": "Rotate PDF", "accept": ["pdf"], "multi": False,
                   "blurb": "Turn every page, or just the ones you list.",
                   "options": {"angle": {"type": "select", "label": "Turn", "default": "90",
                                         "choices": [["90", "90° right"], ["180", "180°"], ["270", "90° left"]]},
                               "pages": {"type": "text", "label": "Pages", "placeholder": "all", "default": ""}}},
    "images-to-pdf": {"title": "Images → PDF", "accept": ["png", "jpg", "webp", "gif", "bmp", "tiff", "heic", "avif"],
                      "multi": True, "blurb": "Turn a stack of photos or scans into one PDF.",
                      "options": {"page": {"type": "select", "label": "Page size", "default": "fit",
                                           "choices": [["fit", "Fit each image"], ["a4", "A4"], ["letter", "US Letter"]]}}},
    "zip": {"title": "Zip files", "accept": ["*"], "multi": True,
            "blurb": "Bundle anything into a single .zip."},
}


def _reader(path):
    from pypdf import PdfReader
    try:
        r = PdfReader(str(path))
        if r.is_encrypted and not r.decrypt(""):
            raise ConversionError(f"{path.name} is password-protected.")
        return r
    except ConversionError:
        raise
    except Exception:
        raise ConversionError(f"{path.name} couldn't be opened as a PDF.")


def run_tool(name, files, opts, job, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    if name == "merge-pdf":
        from pypdf import PdfWriter
        w = PdfWriter()
        for k, f in enumerate(files, 1):
            job.update(k / len(files) * 0.9, f"Adding {f.name}…")
            w.append(_reader(f))
        out = out_dir / "merged.pdf"
        with open(out, "wb") as fh:
            w.write(fh)
        return out

    if name == "split-pdf":
        from pypdf import PdfWriter
        src = files[0]
        r = _reader(src)
        n = len(r.pages)
        spec = (opts.get("ranges") or "").strip()
        groups = []
        if spec:
            for part in [p.strip() for p in spec.split(",") if p.strip()]:
                groups.append(parse_pages(part, n))
        else:
            groups = [[i] for i in range(n)]
        outs = []
        for k, g in enumerate(groups, 1):
            job.update(k / len(groups), f"Writing part {k} of {len(groups)}…")
            w = PdfWriter()
            for i in g:
                w.add_page(r.pages[i])
            label = f"{g[0] + 1}" if len(g) == 1 else f"{g[0] + 1}-{g[-1] + 1}"
            out = out_dir / f"{src.stem}-p{label}.pdf"
            with open(out, "wb") as fh:
                w.write(fh)
            outs.append(out)
        return zip_files(outs, out_dir / f"{src.stem}-split.zip") if len(outs) > 1 else outs[0]

    if name == "compress-pdf":
        from pypdf import PdfWriter
        from PIL import Image
        src = files[0]
        quality, max_side = {"light": (82, 2400), "balanced": (68, 1700), "strong": (50, 1200)}[
            opts.get("strength", "balanced")]
        w = PdfWriter(clone_from=_reader(src))
        pages = w.pages
        for k, page in enumerate(pages, 1):
            job.update(k / len(pages) * 0.9, f"Squeezing page {k} of {len(pages)}…")
            try:
                for img in page.images:
                    pil = img.image
                    if pil is None:
                        continue
                    if max(pil.size) > max_side:
                        pil.thumbnail((max_side, max_side), Image.LANCZOS)
                    if pil.mode not in ("RGB", "L"):
                        pil = pil.convert("RGB")
                    img.replace(pil, quality=quality)
            except Exception:
                pass  # leave unusual images alone
            try:
                page.compress_content_streams()
            except Exception:
                pass
        try:
            w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
        except Exception:
            pass
        out = out_dir / f"{src.stem}-compressed.pdf"
        with open(out, "wb") as fh:
            w.write(fh)
        before, after = src.stat().st_size, out.stat().st_size
        if after >= before:
            shutil.copy(src, out)
            job.note = "Already as small as it gets — kept the original"
        else:
            job.note = f"{100 - after * 100 // before}% smaller"
        return out

    if name == "rotate-pdf":
        from pypdf import PdfWriter
        src = files[0]
        w = PdfWriter(clone_from=_reader(src))
        angle = int(opts.get("angle", "90"))
        for i in parse_pages(opts.get("pages", ""), len(w.pages)):
            w.pages[i].rotate(angle)
        out = out_dir / f"{src.stem}-rotated.pdf"
        with open(out, "wb") as fh:
            w.write(fh)
        return out

    if name == "images-to-pdf":
        from PIL import Image, ImageOps
        from converters.images import flatten
        tools.heif_ok()
        page = opts.get("page", "fit")
        size = {"a4": (1240, 1754), "letter": (1275, 1650)}.get(page)  # 150 dpi
        pages = []
        for k, f in enumerate(files, 1):
            job.update(k / len(files) * 0.85, f"Placing {f.name}…")
            try:
                img = flatten(ImageOps.exif_transpose(Image.open(f)))
            except Exception:
                raise ConversionError(f"{f.name} couldn't be opened as an image.")
            if size:
                pw, ph = size if img.width <= img.height else size[::-1]
                margin = 60
                img.thumbnail((pw - 2 * margin, ph - 2 * margin), Image.LANCZOS)
                canvas = Image.new("RGB", (pw, ph), "white")
                canvas.paste(img, ((pw - img.width) // 2, (ph - img.height) // 2))
                img = canvas
            pages.append(img.convert("RGB"))
        out = out_dir / "images.pdf"
        pages[0].save(out, "PDF", save_all=True, append_images=pages[1:], resolution=150.0)
        return out

    if name == "zip":
        out = out_dir / "files.zip"
        used = set()
        names = []
        for f in files:
            n, i = f.name, 1
            while n in used:
                n = f"{f.stem} ({i}){f.suffix}"
                i += 1
            used.add(n)
            names.append(n)
        return zip_files(files, out, names)

    raise ConversionError("Unknown tool.")
