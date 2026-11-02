"""
Morph — an online file converter.

Run it:        python app.py
Then open:     http://localhost:8080   (in Codespaces the page opens by itself)
"""
import html
import io
import json
import os
import re
import secrets
import sys
import webbrowser
import zipfile
from pathlib import Path

from flask import Flask, abort, g, jsonify, request, send_file, send_from_directory

sys.path.insert(0, str(Path(__file__).parent))

from core import jobs, tools  # noqa: E402
from core.registry import (FORMATS, ROUTES, ConversionError, Context, build,  # noqa: E402
                           catalogue, clean_options, detect_format)
import converters.media  # noqa: E402,F401  (each import registers its conversions)
import converters.images  # noqa: E402,F401
import converters.documents  # noqa: E402,F401
import converters.pdf  # noqa: E402,F401
import converters.data  # noqa: E402,F401
import converters.archives  # noqa: E402,F401
import converters.fonts  # noqa: E402,F401
import youtube  # noqa: E402
from converters.pdf import TOOLS, run_tool  # noqa: E402

HERE = Path(__file__).parent
IN_CODESPACES = os.environ.get("CODESPACES") == "true"
IN_DOCKER = Path("/.dockerenv").exists()
HOST = os.environ.get("MORPH_HOST") or ("0.0.0.0" if (IN_CODESPACES or IN_DOCKER) else "127.0.0.1")
PORT = int(os.environ.get("MORPH_PORT", "8080"))
MAX_MB = int(os.environ.get("MORPH_MAX_UPLOAD_MB", "4096"))
MAX_ACTIVE = int(os.environ.get("MORPH_MAX_ACTIVE", "12"))   # conversions one visitor can run at once
REPO_URL = os.environ.get("MORPH_REPO_URL", "https://github.com/dpatel7-dev/morph")

app = Flask(__name__, static_folder=None)
app.json.sort_keys = False  # keep our own ordering (tools, categories)
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024
if IN_CODESPACES or os.environ.get("MORPH_BEHIND_PROXY") == "1":
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

build()

POPULAR = [("mp4", "mp3"), ("mov", "mp4"), ("heic", "jpg"), ("docx", "pdf"), ("pdf", "docx"), ("png", "jpg"),
           ("webp", "png"), ("mp4", "gif"), ("wav", "mp3"), ("pdf", "jpg"), ("xlsx", "pdf"), ("pptx", "pdf"),
           ("mkv", "mp4"), ("m4a", "mp3"), ("jpg", "pdf"), ("csv", "xlsx"), ("svg", "png"), ("md", "pdf"),
           ("epub", "pdf"), ("json", "yaml"), ("png", "ico"), ("avif", "jpg"), ("ttf", "woff2"), ("srt", "vtt")]

CATALOGUE = catalogue() | {
    "popular": [list(p) for p in POPULAR if p in ROUTES],
    "site": {"max_upload_mb": MAX_MB, "keep_minutes": jobs.KEEP_MINUTES, "repo": REPO_URL, "max_active": MAX_ACTIVE,
             "codespaces": IN_CODESPACES},
}
INDEX = (HERE / "static" / "index.html").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def safe_name(name, fallback="file"):
    name = Path(name or "").name
    name = re.sub(r"[\x00-\x1f<>:\"/\\|?*]", "_", name).strip(" .")
    return name[:180] or fallback


def stem_of(name, fmt_key):
    f = FORMATS.get(fmt_key)
    if f and name.lower().endswith("." + f.ext):  # handles double extensions like .tar.gz
        return name[: -(len(f.ext) + 1)]
    return name.rsplit(".", 1)[0] if "." in name else name


def error(msg, code=400):
    return jsonify({"error": msg}), code


# Each visitor gets a private, random id in a cookie. Jobs are tied to it, so one
# person can never see or download another person's files.
@app.before_request
def identify():
    sid = request.cookies.get("morph_sid", "")
    g.new_sid = not re.fullmatch(r"[A-Za-z0-9_\-]{32,64}", sid)
    g.sid = secrets.token_urlsafe(24) if g.new_sid else sid


@app.after_request
def remember(resp):
    if getattr(g, "new_sid", False):
        resp.set_cookie("morph_sid", g.sid, max_age=60 * 60 * 24 * 30, httponly=True, samesite="Lax",
                        secure=request.is_secure)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return resp


def owned(job_id):
    """The job, if it belongs to whoever is asking."""
    job = jobs.get(job_id)
    if not job or (job.owner and job.owner != g.sid):
        return None
    return job


def owner_id():
    """Browsers get jobs tied to their cookie. Scripts without a cookie get jobs that
    work like a private link: the long random job id is the key."""
    return None if g.new_sid else g.sid


def too_busy():
    return jobs.active_count(owner_id()) >= MAX_ACTIVE


# --------------------------------------------------------------------------
# Pages (the website has real URLs; the browser script draws each page)
# --------------------------------------------------------------------------

def page(title, desc):
    out = INDEX.replace("{{TITLE}}", html.escape(title)).replace("{{DESC}}", html.escape(desc))
    return out, 200, {"Content-Type": "text/html; charset=utf-8"}


DEFAULT_DESC = "Convert video, audio, images, documents, e-books, spreadsheets and more between 127 formats. Free, no sign-up."


@app.get("/")
def home():
    return page("Morph: free online file converter", DEFAULT_DESC)


@app.get("/youtube")
def yt_page():
    return page("YouTube to MP3 and MP4 | Morph", "Save YouTube videos as MP3, M4A, FLAC, MP4, WebM or MKV.")


@app.get("/pdf-tools")
def tools_page():
    return page("PDF tools: merge, split, compress, rotate | Morph", "Merge, split, compress and rotate PDFs, or turn images into a PDF.")


@app.get("/formats")
def formats_page():
    return page("Supported formats | Morph", "Every file format Morph can read and write, and what each one converts to.")


@app.get("/developers")
def dev_page():
    return page("Developer API | Morph", "Convert files from your own code with Morph's HTTP API.")


@app.get("/convert/<pair>")
def convert_page(pair):
    a, _, b = pair.lower().partition("-to-")
    if a in FORMATS and b in FORMATS and (a, b) in ROUTES:
        A, B = FORMATS[a].label, FORMATS[b].label
        return page(f"{A} to {B} converter | Morph",
                    f"Convert {FORMATS[a].name} ({A}) files to {FORMATS[b].name} ({B}) online. Free, no sign-up.")
    if a in FORMATS and not b:
        return page(f"{FORMATS[a].label} converter | Morph", f"Convert {FORMATS[a].name} files to other formats.")
    return page("Morph: free online file converter", DEFAULT_DESC)


@app.get("/static/<path:name>")
def static_files(name):
    return send_from_directory(HERE / "static", name, max_age=300)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@app.get("/api/catalogue")
def api_catalogue():
    return jsonify(CATALOGUE | {"tools": TOOLS, "status": tools.describe(), "youtube": youtube.status(),
                                "max_upload_mb": MAX_MB})


@app.post("/api/convert")
def api_convert():
    up = request.files.get("file")
    target = (request.form.get("target") or "").strip().lower()
    if not up or not up.filename:
        return error("No file was uploaded.")
    name = safe_name(up.filename)
    src_fmt = (request.form.get("source") or "").strip().lower() or detect_format(name)
    if not src_fmt or src_fmt not in FORMATS:
        return error("This file type isn't supported yet.")
    route = ROUTES.get((src_fmt, target))
    if not route:
        return error(f"{FORMATS[src_fmt].label} → {target.upper() or '?'} isn't available.")
    if too_busy():
        return error(f"You already have {MAX_ACTIVE} files converting. Wait for a few to finish, then try again.", 429)
    try:
        raw = json.loads(request.form.get("options") or "{}")
        raw = raw if isinstance(raw, dict) else {}
    except json.JSONDecodeError:
        raw = {}
    opts = clean_options(route.options, raw)

    job = jobs.create("convert", f"{name} → {FORMATS[target].label}", owner=owner_id())
    src_dir = job.dir / "in"
    src_dir.mkdir()
    src = src_dir / name
    up.save(src)
    if src.stat().st_size == 0:
        jobs.remove(job.id)
        return error("That file is empty.")
    ctx = Context(src=src, src_fmt=src_fmt, dst_fmt=target, work=job.dir, opts=opts,
                  stem=safe_name(stem_of(name, src_fmt)), job=job)
    jobs.submit(job, route.fn, ctx)
    return jsonify(job.to_dict() | {"engine": route.engine})


@app.post("/api/tools/<name>")
def api_tool(name):
    if name not in TOOLS:
        return error("Unknown tool.", 404)
    spec = TOOLS[name]
    ups = [u for u in request.files.getlist("files") if u and u.filename]
    if not ups:
        return error("Add at least one file.")
    if not spec["multi"]:
        ups = ups[:1]
    if name == "merge-pdf" and len(ups) < 2:
        return error("Add two or more PDFs to merge.")
    if too_busy():
        return error(f"You already have {MAX_ACTIVE} jobs running. Wait for a few to finish.", 429)
    for u in ups:
        if spec["accept"] != ["*"] and detect_format(u.filename) not in spec["accept"]:
            return error(f"{safe_name(u.filename)} isn't a supported file for this tool.")
    try:
        raw = json.loads(request.form.get("options") or "{}")
        raw = raw if isinstance(raw, dict) else {}
    except json.JSONDecodeError:
        raw = {}
    opts = {}
    for oid, ospec in (spec.get("options") or {}).items():
        val = str(raw.get(oid, ospec.get("default", "")))[:200]
        if ospec["type"] == "select" and val not in [c[0] for c in ospec["choices"]]:
            val = ospec["default"]
        opts[oid] = val
    job = jobs.create("tool", spec["title"], owner=owner_id())
    in_dir = job.dir / "in"
    in_dir.mkdir()
    files = []
    for i, u in enumerate(ups):
        sub = in_dir / f"{i:03}"   # one folder per upload keeps the original names, even duplicates
        sub.mkdir()
        p = sub / safe_name(u.filename)
        u.save(p)
        files.append(p)
    jobs.submit(job, run_tool, name, files, opts, job, job.dir / "out")
    return jsonify(job.to_dict())


@app.post("/api/youtube/info")
def api_yt_info():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(youtube.info(data.get("url")))
    except ConversionError as e:
        return error(str(e))


@app.post("/api/youtube/download")
def api_yt_download():
    data = request.get_json(silent=True) or {}
    if too_busy():
        return error(f"You already have {MAX_ACTIVE} jobs running. Wait for a few to finish.", 429)
    fmt = str(data.get("format") or "mp3").lower()
    quality = str(data.get("quality") or "best")
    title = str(data.get("title") or "Video")[:80]
    job = jobs.create("youtube", f"{title} → {fmt.upper()}", owner=owner_id())
    jobs.submit(job, youtube.download, job, data.get("url"), fmt, quality, bool(data.get("cover", True)),
                job.dir / "out")
    return jsonify(job.to_dict())


@app.get("/api/jobs/<job_id>")
def api_job(job_id):
    job = owned(job_id)
    if not job:
        return error("This job doesn't exist or has expired.", 404)
    return jsonify(job.to_dict())


@app.post("/api/jobs/status")
def api_jobs_status():
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    out = {}
    for jid in ids[:200]:
        j = owned(str(jid))
        out[jid] = j.to_dict() if j else {"id": jid, "status": "expired"}
    return jsonify(out)


@app.get("/api/jobs/<job_id>/download")
def api_download(job_id):
    job = owned(job_id)
    if not job or job.status != "done" or not job.result:
        abort(404)
    return send_file(job.result, as_attachment=True, download_name=job.result.name)


@app.delete("/api/jobs/<job_id>")
def api_cancel(job_id):
    job = owned(job_id)
    if job:
        if job.status in ("queued", "running"):
            job.cancel()
        else:
            jobs.remove(job_id)
    return jsonify({"ok": True})


@app.get("/api/bundle")
def api_bundle():
    ids = [i for i in (request.args.get("ids") or "").split(",") if i][:200]
    buf = io.BytesIO()
    used = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for jid in ids:
            j = owned(jid)
            if not j or j.status != "done" or not j.result:
                continue
            n, k = j.result.name, 1
            while n in used:
                n = f"{j.result.stem} ({k}){j.result.suffix}"
                k += 1
            used.add(n)
            z.write(j.result, n)
    if not used:
        abort(404)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="morph-files.zip", mimetype="application/zip")


@app.errorhandler(413)
def too_big(_e):
    return error(f"That file is bigger than the {MAX_MB} MB limit.", 413)


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return error("Not found.", 404)
    return page("Page not found | Morph", DEFAULT_DESC)[0], 404


# --------------------------------------------------------------------------
# Start
# --------------------------------------------------------------------------

def public_url():
    if IN_CODESPACES and os.environ.get("CODESPACE_NAME"):
        domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
        return f"https://{os.environ['CODESPACE_NAME']}-{PORT}.{domain}"
    return f"http://localhost:{PORT}"


def banner():
    try:
        sys.stdout.reconfigure(errors="replace")  # old Windows consoles can't print ✓
    except Exception:
        pass
    s = tools.describe()
    tick = lambda ok: "✓" if ok else "·"
    print(f"\n  Morph is running →  {public_url()}\n")
    print(f"  {CATALOGUE['total_routes']:,} conversions ready across {len(CATALOGUE['formats'])} formats")
    print(f"  {tick(s['ffmpeg'])} FFmpeg   {tick(s['libreoffice'])} LibreOffice   {tick(s['pandoc'])} Pandoc   "
          f"{tick(s['calibre'])} Calibre   {tick(s['ytdlp'])} yt-dlp   {tick(bool(s['js_runtime']))} JS runtime")
    for item in CATALOGUE["locked"][:4]:
        print(f"  + {item['count']} more with {item['tool']}: {item['how']}")
    print("\n  Press Ctrl+C to stop.\n", flush=True)


if __name__ == "__main__":
    banner()
    if not (IN_CODESPACES or IN_DOCKER) and os.environ.get("MORPH_NO_BROWSER") != "1":
        try:
            webbrowser.open(f"http://localhost:{PORT}")
        except Exception:
            pass
    try:
        from waitress import serve
        serve(app, host=HOST, port=PORT, threads=16, channel_timeout=3600,
              max_request_body_size=MAX_MB * 1024 * 1024, _quiet=True)
    except ImportError:
        app.run(host=HOST, port=PORT, threaded=True, debug=False)
