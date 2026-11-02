"""Archive conversions: ZIP, 7Z, TAR (+ .gz/.bz2/.xz), and RAR (read-only)."""
import os
import tarfile
import zipfile
from pathlib import Path

from core import tools
from core.registry import ConversionError, converter
from core.util import run

ARCH_IN = ["zip", "7z", "tar", "tgz", "tbz2", "txz", "rar"]
ARCH_OUT = ["zip", "7z", "tar", "tgz", "tbz2", "txz"]
MAX_UNPACKED = 16 * 1024 ** 3   # 16 GB: refuse "zip bombs"
MAX_FILES = 200_000


def _reqs(s, d):
    r = []
    if "7z" in (s, d):
        r.append("7zany")
    if s == "rar":
        r.append("7z")
    return r


def extract(ctx, dest):
    f, src = ctx.src_fmt, ctx.src
    ctx.progress(None, "Unpacking…")
    try:
        if f == "zip":
            with zipfile.ZipFile(src) as z:
                infos = z.infolist()
                if any(i.flag_bits & 0x1 for i in infos):
                    raise ConversionError("This ZIP is password-protected, so it can't be repacked.")
                if sum(i.file_size for i in infos) > MAX_UNPACKED or len(infos) > MAX_FILES:
                    raise ConversionError("This archive unpacks to something enormous, so it was skipped for safety.")
                z.extractall(dest)
        elif f in ("tar", "tgz", "tbz2", "txz"):
            with tarfile.open(src) as t:
                members = t.getmembers()
                if sum(m.size for m in members) > MAX_UNPACKED or len(members) > MAX_FILES:
                    raise ConversionError("This archive unpacks to something enormous, so it was skipped for safety.")
                try:
                    t.extractall(dest, filter="data")
                except TypeError:  # very old Python: do the safety check ourselves
                    root = Path(dest).resolve()
                    safe = [m for m in members if (m.isfile() or m.isdir())
                            and str((root / m.name).resolve()).startswith(str(root))]
                    t.extractall(dest, members=safe)
        elif f == "7z" and tools.has_module("py7zr"):
            import py7zr
            with py7zr.SevenZipFile(src) as a:
                if a.needs_password():
                    raise ConversionError("This 7Z is password-protected, so it can't be repacked.")
                if (a.archiveinfo().uncompressed or 0) > MAX_UNPACKED:
                    raise ConversionError("This archive unpacks to something enormous, so it was skipped for safety.")
                a.extractall(dest)
        else:  # 7z / rar through the 7-Zip program
            run([tools.sevenzip(), "x", "-y", "-p", f"-o{dest}", src], ctx,
                friendly="7-Zip couldn't unpack this archive (it may be password-protected).")
    except ConversionError:
        raise
    except (zipfile.BadZipFile, tarfile.TarError, EOFError) as e:
        raise ConversionError(f"This archive looks damaged: {e}")
    if not any(Path(dest).iterdir()):
        raise ConversionError("This archive is empty.")


def pack(ctx, folder: Path, out: Path):
    d = ctx.dst_fmt
    level = ctx.opts.get("level", "normal")
    files = sorted(p for p in folder.rglob("*"))
    ctx.progress(None, "Packing…")
    if d == "zip":
        lvl = {"fast": 1, "normal": 6, "max": 9}[level]
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=lvl) as z:
            for k, p in enumerate(files, 1):
                z.write(p, p.relative_to(folder).as_posix())
                if k % 50 == 0:
                    ctx.check_cancel()
                    ctx.progress(k / len(files), f"Packing {k} of {len(files)}…")
    elif d in ("tar", "tgz", "tbz2", "txz"):
        mode = {"tar": "w", "tgz": "w:gz", "tbz2": "w:bz2", "txz": "w:xz"}[d]
        kw = {}
        if d in ("tgz", "tbz2"):
            kw["compresslevel"] = {"fast": 1, "normal": 6, "max": 9}[level]
        elif d == "txz":
            kw["preset"] = {"fast": 1, "normal": 6, "max": 9}[level]
        with tarfile.open(out, mode, **kw) as t:
            for p in sorted(folder.iterdir()):
                t.add(p, arcname=p.name)
    elif d == "7z":
        if tools.sevenzip():
            mx = {"fast": 1, "normal": 5, "max": 9}[level]
            run([tools.sevenzip(), "a", "-t7z", f"-mx={mx}", "-y", out.resolve(), "."], ctx, cwd=folder,
                friendly="7-Zip couldn't create the archive.")
        else:
            import py7zr
            with py7zr.SevenZipFile(out, "w") as a:
                for p in sorted(folder.iterdir()):
                    a.writeall(p, arcname=p.name)
    return out


def repack(ctx):
    folder = ctx.tmp("unpacked")
    folder.mkdir(exist_ok=True)
    extract(ctx, folder)
    out = ctx.out()
    return pack(ctx, folder, out)


# Each route gets its own requirements (7Z and RAR need extra helpers)
for _s in ARCH_IN:
    for _d in ARCH_OUT:
        if _s != _d:
            converter([_s], [_d], options=["level"] if _d != "tar" else [], requires=_reqs(_s, _d),
                      engine="Python")(repack)
