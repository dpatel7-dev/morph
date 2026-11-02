# Morph

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/dpatel7-dev/morph)

A free online file converter. It does about 2,100 conversions between 127+ formats, plus YouTube → MP3/MP4 and PDF tools.

- **Convert:** video, audio, images, SVG, Word, Excel, PowerPoint, PDF, Markdown, LaTeX, e-books (including Kindle), JSON, YAML, XML, CSV, archives, fonts and subtitles. Every pair has its own page, for example `/convert/mp4-to-mp3`.
- **YouTube:** paste a link, then save it as MP3, M4A, WAV, FLAC, Opus, MP4, WebM or MKV, in any quality up to 4K.
- **PDF tools:** merge, split, compress and rotate PDFs, turn images into a PDF, and zip files.
- **Formats:** a searchable list of every format and what it converts to.
- **Developers:** an HTTP API that does everything the website does.

Each visitor's files are private to them, and everything is deleted automatically after an hour.

---

## Run it in GitHub Codespaces (easiest)

Codespaces runs Morph on a computer in the cloud, with every converter engine already installed. You only need a web browser.

1. Click the **Open in GitHub Codespaces** button at the top of this page.
   Or go to the repo on GitHub, click the green **Code** button, open the **Codespaces** tab, and click **Create codespace on main**.
2. Wait while it builds. **The first time takes about 5 to 10 minutes**, because it installs LibreOffice, FFmpeg, Calibre and the rest. Later starts take under a minute.
3. When it's ready, a terminal at the bottom shows **Morph is running**, and Morph opens in a new browser tab.
   - If the tab doesn't open, click the **Ports** tab at the bottom. Find **Morph website (8080)** and click the globe icon.
4. Use the site just like any other website.

**Stopping and starting again**
- Codespaces stops by itself after 30 minutes of not being used. You can also stop it yourself at <https://github.com/codespaces>: click **…** next to it, then **Stop codespace**.
- To start it again, go to <https://github.com/codespaces> and click it. Morph starts automatically.
- GitHub gives free accounts a monthly allowance of Codespaces hours. Stopping it when you're done saves those hours.

**Sharing it with someone**
The website address is private to you by default; only your GitHub account can open it. To let a friend use it, open the **Ports** tab, right-click **8080**, and choose **Port Visibility → Public**. Anyone with the link can then use it while your codespace is running, so switch it back to Private afterwards.

---

## Run it on your own computer (optional)

**Windows**
1. Install Python from <https://www.python.org/downloads/>. On the first screen, tick **"Add python.exe to PATH"**.
2. Download this repo: click the green **Code** button, then **Download ZIP**, then unzip it.
3. Double-click **`start-windows.bat`**. The first start takes 2 to 5 minutes; your browser then opens **http://localhost:8080**.

**Mac / Linux**
```bash
./start-mac-linux.sh
```

On your own computer, Morph works straight away for video, audio, images, PDF, Markdown, data files, archives and fonts. Install these to unlock the rest, then restart Morph:

| Helper | What it adds | Windows (PowerShell) | Mac (Homebrew) |
|---|---|---|---|
| Deno | Reliable YouTube downloads | `winget install --id=DenoLand.Deno` | `brew install deno` |
| LibreOffice | Word, Excel, PowerPoint, Pages, Keynote | `winget install TheDocumentFoundation.LibreOffice` | `brew install --cask libreoffice` |
| Calibre | Kindle formats (MOBI, AZW3, …) | `winget install calibre.calibre` | `brew install --cask calibre` |
| Tesseract | Reading text in pictures | `winget install UB-Mannheim.TesseractOCR` | `brew install tesseract` |
| ImageMagick | SVG images | `winget install ImageMagick.ImageMagick` | `brew install librsvg` |
| 7-Zip | RAR archives | `winget install 7zip.7zip` | `brew install sevenzip` |

## Run it with Docker

```bash
docker build -t morph .
docker run -p 8080:8080 morph
```

The Docker image comes with every engine installed.

---

## When something goes wrong

| Problem | Fix |
|---|---|
| A YouTube video won't download | Restart Morph; it updates the YouTube downloader each time it starts. YouTube sometimes blocks cloud computers (including Codespaces) and asks for a sign-in "to confirm you're not a bot". If that happens, wait a while or run Morph on your own computer. |
| The Codespace says "This codespace is starting" for a long time | The first build takes up to 10 minutes. If it fails, open the **Command Palette** (`Ctrl`+`Shift`+`P`) and run **Codespaces: Rebuild Container**. |
| The site stopped working in Codespaces | The terminal running Morph was closed. Open a new terminal (`Ctrl`+`` ` ``) and type `python app.py`. |
| "Address already in use" | Morph is already running in another terminal. Use that one, or close it first. |

---

## Settings

Set these environment variables before starting Morph:

| Variable | Default | What it does |
|---|---|---|
| `MORPH_PORT` | `8080` | The website's port |
| `MORPH_HOST` | `127.0.0.1` (`0.0.0.0` in Codespaces/Docker) | Which network address to listen on |
| `MORPH_MAX_UPLOAD_MB` | `4096` | The largest upload allowed |
| `MORPH_KEEP_MINUTES` | `60` | How long files are kept |
| `MORPH_MAX_ACTIVE` | `12` | How many jobs one visitor can run at once |
| `MORPH_WORKERS` | 2 to 4 | How many conversions run at the same time |
| `MORPH_BEHIND_PROXY` | (off) | Set to `1` when hosting behind a reverse proxy (nginx, Caddy, …) |
| `MORPH_REPO_URL` | this repo | Where the GitHub links point |

**Hosting it publicly:** Morph has no accounts or rate limits beyond `MORPH_MAX_ACTIVE`, and converting video uses a lot of computing power. Put it behind a reverse proxy with HTTPS, keep `MORPH_MAX_UPLOAD_MB` sensible, and keep in mind that the YouTube feature may break the terms of service of the sites it downloads from.

---

## For developers

```
app.py                 web server, pages and API (Flask + Waitress)
youtube.py             YouTube downloads (yt-dlp)
core/registry.py       every format, option and conversion route
core/tools.py          finds FFmpeg, LibreOffice, Pandoc, Calibre, …
core/jobs.py           background jobs, progress, privacy, clean-up
converters/            media, images, documents, pdf, data, archives, fonts
static/                the website: plain HTML, CSS and JavaScript (no build step)
.devcontainer/         GitHub Codespaces setup
```

**Checking it works:** `python tests/smoke_test.py` makes sample files and runs about 100 real conversions.

**Adding a conversion.** Write a function that takes `ctx` and returns the path of the file it made, then register it:

```python
from core.registry import converter

@converter(["mp4", "mov"], ["mp3"], options=["abitrate"], requires=["ffmpeg"], engine="FFmpeg")
def my_converter(ctx):
    out = ctx.out()                  # output path, named after the upload
    ...                              # read ctx.src, use ctx.opts, call ctx.progress(0.5, "Halfway…")
    return out
```

The website, the formats page and the API pick up new routes automatically. Routes whose engines aren't installed are hidden, and the Developers page lists what's missing.

**API quick start**

```bash
curl -F "file=@holiday.mov" -F "target=mp4" http://localhost:8080/api/convert   # → {"id": "…"}
curl http://localhost:8080/api/jobs/<id>                                        # → {"status": "done", …}
curl -OJ http://localhost:8080/api/jobs/<id>/download
```

In a browser, jobs are tied to a private cookie, so one visitor can never open another's files. From scripts without a cookie, the 32-character job id works like a private link. The full reference is on the site's **Developers** page.

> Only download videos you own or have permission to save. Downloading may break a site's terms of service.
