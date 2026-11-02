"""
Background jobs. Each upload becomes a Job that runs on a worker thread, so the
website can poll for progress while big files convert.
"""
import os
import shutil
import tempfile
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .registry import Cancelled, ConversionError

DATA_DIR = Path(os.environ.get("MORPH_DATA") or Path(tempfile.gettempdir()) / "morph-jobs")
DATA_DIR.mkdir(parents=True, exist_ok=True)
KEEP_MINUTES = int(os.environ.get("MORPH_KEEP_MINUTES", "60"))
WORKERS = int(os.environ.get("MORPH_WORKERS", str(max(2, min(4, (os.cpu_count() or 2) // 2)))))

_executor = ThreadPoolExecutor(max_workers=WORKERS)
_jobs: dict[str, "Job"] = {}
_lock = threading.Lock()


class Job:
    def __init__(self, kind, title, owner=None):
        self.id = uuid.uuid4().hex          # 128 random bits: impossible to guess
        self.owner = owner                  # the visitor who started it
        self.kind = kind            # "convert", "tool" or "youtube"
        self.title = title
        self.status = "queued"      # queued -> running -> done | error | cancelled
        self.progress = None        # 0..1, or None when unknown
        self.message = "Waiting in line…"
        self.error = None
        self.code = None            # machine-readable error kind, e.g. "needs_cookies"
        self.result = None          # Path of the finished file
        self.created = time.time()
        self.finished = None
        self.cancelled = False
        self.proc = None            # running subprocess, so cancel can stop it
        self.note = None            # optional message to show when finished
        self.dir = DATA_DIR / self.id
        self.dir.mkdir(parents=True, exist_ok=True)

    def update(self, fraction=None, message=None):
        if fraction is not None:
            self.progress = max(0.0, min(1.0, float(fraction)))
        if message is not None:
            self.message = message

    def cancel(self):
        self.cancelled = True
        p = self.proc
        if p and p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass

    def to_dict(self):
        d = {
            "id": self.id, "kind": self.kind, "title": self.title, "status": self.status,
            "progress": self.progress, "message": self.message, "error": self.error, "note": self.note,
            "code": self.code,
        }
        if self.result and self.result.exists():
            d["file"] = {"name": self.result.name, "size": self.result.stat().st_size}
            d["elapsed"] = round((self.finished or time.time()) - self.created, 1)
        return d


def create(kind, title, owner=None):
    job = Job(kind, title, owner)
    with _lock:
        _jobs[job.id] = job
    return job


def get(job_id):
    with _lock:
        return _jobs.get(job_id)


def active_count(owner):
    with _lock:
        return sum(1 for j in _jobs.values() if j.owner == owner and j.status in ("queued", "running"))


def submit(job, fn, *args):
    """Run fn(*args) in the background. fn must return the Path of the result."""
    def runner():
        if job.cancelled:
            job.status = "cancelled"
            return
        job.status = "running"
        job.message = "Working…"
        try:
            out = fn(*args)
            if job.cancelled:
                raise Cancelled()
            if not out or not Path(out).exists() or Path(out).stat().st_size == 0:
                raise ConversionError("The converter finished but produced an empty file.")
            job.result = Path(out)
            job.progress = 1.0
            job.message = job.note or "Done"
            job.status = "done"
        except Cancelled:
            job.status = "cancelled"
            job.message = "Cancelled"
        except ConversionError as e:
            job.status = "error"
            job.error = str(e)
            job.code = getattr(e, "code", None)
        except Exception as e:  # unexpected: keep the details in the console
            traceback.print_exc()
            job.status = "error"
            job.error = f"Something went wrong: {e}"
        finally:
            job.finished = time.time()
            job.proc = None

    _executor.submit(runner)
    return job


def remove(job_id):
    with _lock:
        job = _jobs.pop(job_id, None)
    if job:
        job.cancel()
        shutil.rmtree(job.dir, ignore_errors=True)


def _janitor():
    """Delete finished jobs (and their files) after KEEP_MINUTES."""
    while True:
        time.sleep(60)
        cutoff = time.time() - KEEP_MINUTES * 60
        with _lock:
            old = [j.id for j in _jobs.values() if j.finished and j.finished < cutoff]
        for jid in old:
            remove(jid)
        # Folders left behind by a previous run of the app
        try:
            for d in DATA_DIR.iterdir():
                if d.is_dir() and d.name not in _jobs and d.stat().st_mtime < cutoff:
                    shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


threading.Thread(target=_janitor, daemon=True).start()
