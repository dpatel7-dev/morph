"""
Quick check that Morph works on this machine:   python tests/smoke_test.py

Makes a few small sample files, converts each one to every format it supports
through the real API, and prints a summary.
"""
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app as morph  # noqa: E402
from core import tools  # noqa: E402

# Results a sample file can't give (no subtitle track, no text in the picture) aren't failures
EXPECTED = ("subtitle track", "readable text", "subtitles are stored")


def make_samples(d: Path):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (240, 160), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((20, 20, 140, 140), fill=(240, 90, 70, 255))
    img.save(d / "logo.png")
    (d / "notes.md").write_text("# Notes\n\nSome **bold** text.\n\n- one\n- two\n", encoding="utf-8")
    (d / "people.csv").write_text("name,age\nAna,31\nBen,27\n", encoding="utf-8")
    (d / "config.json").write_text(json.dumps({"app": {"name": "Morph", "tags": ["a", "b"]}}), encoding="utf-8")
    (d / "talk.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    if tools.ffmpeg():
        subprocess.run([tools.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=15",
                        "-f", "lavfi", "-i", "sine=d=1", "-t", "1", "-pix_fmt", "yuv420p", "-shortest", str(d / "clip.mp4")],
                       check=True)


def main():
    work = Path(tempfile.mkdtemp(prefix="morph-smoke-"))
    make_samples(work)
    client = morph.app.test_client()
    client.get("/")
    morph.MAX_ACTIVE = 10_000
    pending, results = {}, []
    for f in sorted(work.iterdir()):
        src = morph.detect_format(f.name)
        for dst, _ in morph.CATALOGUE["routes"].get(src, []):
            r = client.post("/api/convert", data={"file": (io.BytesIO(f.read_bytes()), f.name), "target": dst},
                            content_type="multipart/form-data")
            j = r.get_json()
            if r.status_code == 200:
                pending[j["id"]] = (f.name, dst)
            else:
                results.append((f.name, dst, "error", j.get("error")))
    start = time.time()
    while pending and time.time() - start < 600:
        time.sleep(0.5)
        for jid in list(pending):
            j = client.get(f"/api/jobs/{jid}").get_json()
            if j["status"] in ("done", "error", "cancelled"):
                name, dst = pending.pop(jid)
                results.append((name, dst, j["status"], j.get("error")))
    shutil.rmtree(work, ignore_errors=True)
    ok = [r for r in results if r[2] == "done"]
    expected = [r for r in results if r[2] != "done" and r[3] and any(e in r[3] for e in EXPECTED)]
    bad = [r for r in results if r[2] != "done" and r not in expected]
    print(f"\n  {len(ok)} conversions worked, {len(expected)} skipped as expected, {len(bad)} failed")
    for name, dst, _, err in bad:
        print(f"  FAILED  {name} → {dst}: {err}")
    sys.exit(1 if bad or pending else 0)


if __name__ == "__main__":
    main()
