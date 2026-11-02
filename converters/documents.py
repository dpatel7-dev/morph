"""
Office documents, spreadsheets, presentations (LibreOffice), markup formats
(Pandoc) and e-books (Calibre / Pandoc).
"""
import os
import shutil
import threading
import time
from pathlib import Path

from core import tools
from core.jobs import DATA_DIR
from core.registry import ConversionError, converter
from core.util import one_or_zip, run, zip_files

# --------------------------------------------------------------------------
# LibreOffice
# --------------------------------------------------------------------------

_LO_LOCK = threading.Lock()  # LibreOffice runs one document at a time per profile
LO_PROFILE = DATA_DIR.parent / "morph-libreoffice-profile"

LO_TARGET = {
    "pdf": "pdf", "docx": "docx:MS Word 2007 XML", "doc": "doc:MS Word 97", "odt": "odt", "rtf": "rtf",
    "txt": "txt:Text (encoded):UTF8", "html": "html", "epub": "epub",
    "xlsx": "xlsx:Calc MS Excel 2007 XML", "xls": "xls:MS Excel 97", "ods": "ods",
    "csv": "csv:Text - txt - csv (StarCalc):44,34,76,1", "tsv": "csv:Text - txt - csv (StarCalc):9,34,76,1",
    "pptx": "pptx:Impress MS PowerPoint 2007 XML", "ppt": "ppt:MS PowerPoint 97", "odp": "odp",
}
LO_INFILTER = {"csv": "CSV:44,34,76,1", "tsv": "CSV:9,34,76,1", "html": "HTML (StarWriter)",
               "pdf": "writer_pdf_import"}


def soffice(ctx, src, target, infilter=None, label="Converting with LibreOffice…"):
    out_dir = ctx.tmp("lo-out")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir()
    cmd = [tools.soffice(), f"-env:UserInstallation={LO_PROFILE.resolve().as_uri()}", "--headless",
           "--norestore", "--nologo", "--nodefault", "--nolockcheck"]
    if infilter:
        cmd.append(f"--infilter={infilter}")
    cmd += ["--convert-to", target, "--outdir", out_dir, src]
    env = dict(os.environ)
    env.setdefault("HOME", str(DATA_DIR.parent))
    ctx.progress(None, "Waiting for LibreOffice…" if _LO_LOCK.locked() else label)
    with _LO_LOCK:
        ctx.check_cancel()
        ctx.progress(None, label)
        run(cmd, ctx, timeout=900, env=env, friendly="LibreOffice couldn't convert this file.")
    files = sorted(f for f in out_dir.rglob("*") if f.is_file())
    for _ in range(40):  # some systems hand back control a moment before the file lands
        if files:
            break
        time.sleep(0.25)
        files = sorted(f for f in out_dir.rglob("*") if f.is_file())
    if not files:
        raise ConversionError("LibreOffice couldn't open this file. It may be password-protected, damaged, "
                              "or not really the format its name says.")
    return files


def finish(ctx, files, main_ext=None):
    """Move the main output into place; zip it together with any side files (e.g. HTML images)."""
    main_ext = main_ext or ctx.dst.ext
    main = next((f for f in files if f.name.lower().endswith("." + main_ext.split(".")[-1])), files[0])
    out = ctx.out()
    if len(files) == 1:
        shutil.move(str(main), out)
        return out
    shutil.move(str(main), out)
    others = [f for f in files if f != main]
    dest = ctx.work / "out" / f"{ctx.stem}.zip"
    return zip_files([out] + others, dest, [out.name] + [f"{ctx.stem}_files/{f.name}" for f in others])


WRITER_IN = ["docx", "doc", "odt", "rtf", "txt", "html", "pages", "wpd", "wps", "docm", "dotx"]
WRITER_OUT = ["pdf", "docx", "doc", "odt", "rtf", "txt", "html", "epub"]
CALC_IN = ["xlsx", "xls", "ods", "csv", "tsv", "xlsm", "numbers"]
CALC_OUT = ["xlsx", "xls", "ods", "csv", "tsv", "pdf", "html"]
IMPRESS_IN = ["pptx", "ppt", "odp", "key", "ppsx", "pps"]
IMPRESS_OUT = ["pptx", "ppt", "odp", "pdf"]


@converter(WRITER_IN, WRITER_OUT, requires=["soffice"], priority=2, engine="LibreOffice")
@converter([c for c in CALC_IN if c not in ("csv", "tsv")], CALC_OUT, requires=["soffice"], priority=0,
           engine="LibreOffice")
@converter(["csv", "tsv"], [c for c in CALC_OUT if c != "html"], requires=["soffice"], priority=0,
           engine="LibreOffice")
@converter(IMPRESS_IN, IMPRESS_OUT, requires=["soffice"], priority=2, engine="LibreOffice")
@converter(["pdf"], ["docx", "odt", "rtf", "doc"], requires=["soffice"], priority=0, engine="LibreOffice")
def libreoffice(ctx):
    target = LO_TARGET[ctx.dst_fmt]
    if ctx.dst_fmt == "html" and ctx.src_fmt in CALC_IN:
        target = "html:HTML (StarCalc)"
    infilter = LO_INFILTER.get(ctx.src_fmt)
    if ctx.src_fmt == "html" and ctx.dst_fmt == "pdf":
        infilter = None
    files = soffice(ctx, ctx.src, target, infilter)
    return finish(ctx, files, "csv" if ctx.dst_fmt == "tsv" else None)


@converter(IMPRESS_IN, ["png", "jpg"], options=["dpi", "pages"], requires=["soffice", "py:pypdfium2"],
           priority=2, engine="LibreOffice")
def slides_to_images(ctx):
    from converters.pdf import render_pdf
    pdf = soffice(ctx, ctx.src, "pdf", label="Laying out slides…")[0]
    return render_pdf(ctx, pdf, label="slides")


# --------------------------------------------------------------------------
# Pandoc
# --------------------------------------------------------------------------

PD_READ = {"md": "markdown", "html": "html", "docx": "docx", "odt": "odt", "epub": "epub", "rst": "rst",
           "tex": "latex", "org": "org", "textile": "textile", "mediawiki": "mediawiki", "ipynb": "ipynb",
           "fb2": "fb2", "typ": "typst", "dbk": "docbook", "opml": "opml", "adoc": "asciidoc", "rtf": "rtf"}
PD_WRITE = {"md": "gfm", "html": "html5", "docx": "docx", "odt": "odt", "epub": "epub3", "rst": "rst",
            "tex": "latex", "org": "org", "textile": "textile", "mediawiki": "mediawiki", "adoc": "asciidoc",
            "rtf": "rtf", "txt": "plain", "ipynb": "ipynb", "fb2": "fb2", "pptx": "pptx", "typ": "typst",
            "dbk": "docbook5"}
STANDALONE = {"html", "tex", "rtf", "fb2", "typ", "dbk", "epub", "docx", "odt", "pptx", "ipynb"}
TEXT_OUT = {"md", "rst", "org", "textile", "mediawiki", "adoc", "tex", "typ", "txt", "dbk"}
OFFICE = {"docx", "odt", "rtf", "doc", "txt", "epub"}


def pandoc(ctx, src, src_fmt, out, dst_fmt):
    work = ctx.tmp("pandoc")
    work.mkdir(exist_ok=True)
    cmd = [tools.pandoc(), "-f", PD_READ[src_fmt], "-t", PD_WRITE[dst_fmt], "-o", out, Path(src).resolve()]
    if dst_fmt in STANDALONE:
        cmd.insert(1, "--standalone")
    if dst_fmt in TEXT_OUT or dst_fmt == "html":
        cmd.insert(1, "--wrap=none")
    if src_fmt in ("docx", "odt", "epub") and dst_fmt in TEXT_OUT:
        cmd.insert(1, "--extract-media=media")
    cmd[1:1] = ["-M", f"pagetitle={ctx.stem}"]
    embed = ["--embed-resources"] if tools.pandoc_version() >= (2, 19) else ["--self-contained"]
    ctx.progress(None, "Converting with Pandoc…")
    if dst_fmt == "html":
        try:
            run(cmd[:1] + embed + cmd[1:], ctx, cwd=work, friendly="Pandoc couldn't convert this file.")
            return work
        except ConversionError:
            pass  # usually a missing linked image; try again without embedding
    run(cmd, ctx, cwd=work, friendly="Pandoc couldn't convert this file.")
    return work


def _pandoc_requires(s, d):
    return ["pandoc", f"pandoc-r:{PD_READ[s]}", f"pandoc-w:{PD_WRITE[d]}"]


def pandoc_route(ctx):
    out = ctx.out()
    work = pandoc(ctx, ctx.src, ctx.src_fmt, out.resolve(), ctx.dst_fmt)
    media = work / "media"
    if media.exists() and any(media.rglob("*")):
        files = [p for p in media.rglob("*") if p.is_file()]
        dest = ctx.work / "out" / f"{ctx.stem}.zip"
        return zip_files([out] + files, dest, [out.name] + [f"media/{p.relative_to(media).as_posix()}" for p in files])
    return out


for _s in PD_READ:
    for _d in PD_WRITE:
        if _s == _d:
            continue
        # Prefer LibreOffice between office formats, Pandoc for everything else
        prio = 1 if (_s in OFFICE and _d in OFFICE) else 3
        if (_s, _d) in {("docx", "html"), ("odt", "html"), ("html", "docx"), ("html", "odt")}:
            prio = 3
        converter([_s], [_d], requires=_pandoc_requires(_s, _d), priority=prio, engine="Pandoc")(pandoc_route)


def markup_to_pdf(ctx):
    mid = ctx.tmp(f"{ctx.stem}.docx")
    pandoc(ctx, ctx.src, ctx.src_fmt, mid.resolve(), "docx")
    files = soffice(ctx, mid, "pdf", label="Typesetting PDF…")
    return finish(ctx, files)


for _s in ["md", "rst", "tex", "org", "textile", "mediawiki", "ipynb", "fb2", "epub", "typ", "dbk", "adoc", "opml"]:
    converter([_s], ["pdf"], requires=["soffice", "pandoc", f"pandoc-r:{PD_READ[_s]}"], priority=1,
              engine="Pandoc + LibreOffice")(markup_to_pdf)


def markup_to_office(ctx):
    mid = ctx.tmp(f"{ctx.stem}.docx")
    pandoc(ctx, ctx.src, ctx.src_fmt, mid.resolve(), "docx")
    files = soffice(ctx, mid, LO_TARGET[ctx.dst_fmt])
    return finish(ctx, files)


for _s in ["md", "rst", "tex", "org", "textile", "mediawiki", "ipynb", "fb2", "epub", "typ", "adoc"]:
    converter([_s], ["doc"], requires=["soffice", "pandoc", f"pandoc-r:{PD_READ[_s]}"], priority=1,
              engine="Pandoc + LibreOffice")(markup_to_office)


# --------------------------------------------------------------------------
# Calibre (e-books)
# --------------------------------------------------------------------------

EBOOKS = {"epub", "mobi", "azw3", "fb2", "lit", "pdb", "lrf", "htmlz", "txtz", "snb", "tcr", "cbz"}
CAL_IN = ["epub", "mobi", "azw3", "fb2", "lit", "pdb", "lrf", "htmlz", "txtz", "snb", "tcr", "cbz",
          "docx", "odt", "rtf", "txt", "html", "pdf", "md"]
CAL_OUT = ["epub", "mobi", "azw3", "fb2", "pdf", "docx", "txt", "rtf", "htmlz", "pdb", "lrf", "snb",
           "tcr", "txtz", "lit"]


def calibre(ctx):
    src = ctx.src
    if ctx.src_fmt == "md":  # Calibre reads Markdown through its TXT reader
        src = ctx.tmp(f"{ctx.stem}.txt")
        shutil.copy(ctx.src, src)
    out = ctx.out()
    cmd = [tools.calibre(), src, out]
    if ctx.src_fmt == "md":
        cmd += ["--formatting-type", "markdown", "--paragraph-type", "off"]
    ctx.progress(None, "Converting with Calibre…")
    run(cmd, ctx, timeout=900, friendly="Calibre couldn't convert this book.")
    return out


for _s in CAL_IN:
    for _d in CAL_OUT:
        if _s != _d and (_s in EBOOKS or _d in EBOOKS):
            converter([_s], [_d], requires=["calibre"], priority=4, engine="Calibre")(calibre)
