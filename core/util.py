"""Small helpers shared by the converters."""
import os
import re
import subprocess
import threading
import time
import zipfile
from pathlib import Path

from .registry import Cancelled, ConversionError

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def run(cmd, ctx=None, timeout=1800, cwd=None, env=None, on_line=None, friendly="The converter failed."):
    """
    Run a helper program. Stops early if the job is cancelled.
    If `on_line` is given it receives each line of the program's stdout (for progress).
    Raises ConversionError with the tail of the program's error output on failure.
    """
    cmd = [str(c) for c in cmd]
    log_path = None
    if ctx is not None:
        log_path = ctx.tmp(f"log-{int(time.time() * 1000)}.txt")
    log = open(log_path, "w+", encoding="utf-8", errors="replace") if log_path else subprocess.DEVNULL
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE if on_line else subprocess.DEVNULL,
                                stderr=log, stdin=subprocess.DEVNULL, cwd=cwd, env=env,
                                text=True, errors="replace", creationflags=CREATE_NO_WINDOW)
    except FileNotFoundError:
        raise ConversionError(f"Could not start {Path(cmd[0]).name}. Is it installed?")
    if ctx is not None and ctx.job:
        ctx.job.proc = proc

    killed = {"timeout": False}

    def watchdog():
        start = time.time()
        while proc.poll() is None:
            if ctx is not None and ctx.job and ctx.job.cancelled:
                proc.kill()
                return
            if time.time() - start > timeout:
                killed["timeout"] = True
                proc.kill()
                return
            time.sleep(0.25)

    threading.Thread(target=watchdog, daemon=True).start()
    try:
        if on_line:
            for line in proc.stdout:
                on_line(line.rstrip("\n"))
        proc.wait()
        if ctx is not None and ctx.job:
            ctx.job.proc = None
            if ctx.job.cancelled:
                raise Cancelled()
        if killed["timeout"]:
            raise ConversionError("This conversion took too long and was stopped.")
        if proc.returncode != 0:
            detail = ""
            if log_path:
                log.seek(0)
                lines = [l.strip() for l in log.read().splitlines() if l.strip()]
                detail = " ".join(lines[-3:])[:400]
            raise ConversionError(f"{friendly} {detail}".strip())
        return proc.returncode
    finally:
        if log is not subprocess.DEVNULL:
            log.close()


def zip_files(files, dest: Path, arcnames=None):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for i, f in enumerate(files):
            z.write(f, arcnames[i] if arcnames else Path(f).name)
    return dest


def one_or_zip(files, ctx, label="pages"):
    """Return the single file, or zip several outputs together."""
    files = [Path(f) for f in files]
    if not files:
        raise ConversionError("Nothing was produced.")
    if len(files) == 1:
        final = ctx.out(suffix="")
        if files[0] != final:
            files[0].replace(final)
        return final
    dest = ctx.work / "out" / f"{ctx.stem}-{label}.zip"
    dest.parent.mkdir(exist_ok=True)
    return zip_files(files, dest)


def parse_pages(spec: str, total: int):
    """'1-3, 7' -> [0, 1, 2, 6] (zero-based). Blank means every page."""
    spec = (spec or "").strip().lower()
    if not spec or spec == "all":
        return list(range(total))
    pages = []
    for part in re.split(r"[,\s]+", spec):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)?-(\d+)?", part)
        if m:
            a = int(m.group(1) or 1)
            b = int(m.group(2) or total)
            pages.extend(range(a - 1, min(b, total)))
        elif part.isdigit():
            if 1 <= int(part) <= total:
                pages.append(int(part) - 1)
        else:
            raise ConversionError(f"I couldn't read the page list “{spec}”. Try something like 1-3, 7.")
    seen, ordered = set(), []
    for p in pages:
        if 0 <= p < total and p not in seen:
            seen.add(p)
            ordered.append(p)
    if not ordered:
        raise ConversionError(f"Those pages aren't in this file (it has {total}).")
    return ordered


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
