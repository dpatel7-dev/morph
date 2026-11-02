# Morph

Morph is an "anything to anything" converter. It contains a large library of different file types to convert to: about 2,000 conversions between 127 formats. It also has a YouTube to MP3/MP4 converter and a set of PDF tools.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/dpatel7-dev/morph)

![The Morph home page](docs/images/home.png)

**On this page:**
[Start Morph](#start-morph) ·
[Convert files](#convert-files) ·
[Change the settings](#change-the-settings) ·
[Convert lots of files at once](#convert-lots-of-files-at-once) ·
[YouTube to MP3 or MP4](#youtube-to-mp3-or-mp4) ·
[PDF tools](#pdf-tools) ·
[What it can convert](#what-it-can-convert) ·
[Good to know](#good-to-know) ·
[If something goes wrong](#if-something-goes-wrong) ·
[Run it on your own computer](#run-it-on-your-own-computer) ·
[For developers](#for-developers)

---

## Start Morph

The easiest way is **GitHub Codespaces**. It runs Morph on a computer in the cloud with everything already installed, so all you need is a web browser.

1. Click the **Open in GitHub Codespaces** button at the top of this page.
2. On the next page, click **Create codespace**.
3. Wait while it sets up. **The very first time takes about 5–10 minutes** because it installs all the converters. After that it starts in under a minute.
4. When it's ready, Morph opens in a new browser tab.
   - Didn't open? At the bottom of the Codespaces window, click the **Ports** tab. Next to **Morph website (8080)**, click the 🌐 globe icon.

**When you're done:** Codespaces stops by itself after 30 minutes of not being used. To stop it sooner (and save your free monthly hours), go to [github.com/codespaces](https://github.com/codespaces), click **⋯** next to your codespace, and choose **Stop codespace**.

**Next time:** go to [github.com/codespaces](https://github.com/codespaces) and click your codespace. Morph starts automatically.

---

## Convert files

1. Click **Choose files**. You can also drag files onto the box, or paste a copied file with `Ctrl` + `V` (`⌘` + `V` on a Mac).
2. Each file appears in a list. Morph picks a format for it next to the word **to**.
3. To pick a different format, click it. Choose a family on the left (Video, Audio, Image…) and then a format, or type in the search box, for example `jpg`.
4. Click **Convert**.
5. When a file says **Done**, click **Download**.

![Picking a format for a file](docs/images/picker.png)

![Converted files, ready to download](docs/images/done.png)

### Choose the format first

At the top of the box, use **Convert [Any format] to [Choose format]**. If you pick **to → MP3**, every file you add after that is set to MP3.

Every pair also has its own page you can bookmark, like `/convert/mp4-to-mp3` or `/convert/heic-to-jpg`. The **Popular conversions** on the home page link to the most common ones.

![The MP4 to MP3 page](docs/images/pair.png)

---

## Change the settings

Click the **sliders icon** (next to the format) to see the settings for that file. What you can change depends on the format you're converting to:

| Converting to | Settings you can change |
|---|---|
| **Video** (MP4, WebM, MOV…) | Resolution (4K to 240p), quality, codec (H.264, H.265, AV1), frame rate, remove the sound, start and end time |
| **Audio** (MP3, WAV, FLAC…) | Bitrate, sample rate, stereo or mono, volume, even out loudness, start and end time |
| **GIF** | Frame rate, width, start and end time |
| **Images** (JPG, PNG, WebP…) | Quality, width and height, rotate, flip, black & white, background colour for see-through areas, keep photo info |
| **PDF → images** | Sharpness (dpi) and which pages, like `1-3, 7` |
| **Data** (JSON, CSV, Excel…) | Pretty or compact, detect numbers, which Excel sheet |
| **Archives** (ZIP, 7Z…) | How hard to compress |

![The settings for converting a video to MP3](docs/images/options.png)

**Tips**
- **Start and end times** are written as minutes:seconds. `1:30` means 1 minute 30 seconds, `90` also works, and `1:02:00` is 1 hour 2 minutes.
- **Shrink or resize without changing format:** pick the same format again. For example, MP4 → MP4 at 720p makes a video much smaller, and JPG → JPG with a width of 1200 resizes a photo.
- A **blue dot** on the sliders icon means you've changed something from the defaults.

---

## Convert lots of files at once

- Add as many files as you like, of any mix of types.
- **All to** (top right of the list) changes every file to one format at once. It only shows formats that every file in the list can become.
- **Convert 5 files** starts them all together.
- **Download all (.zip)** saves every finished file in one go.
- Changed your mind? Pick a new format or setting on a finished file, and it's ready to convert again.

---

## YouTube to MP3 or MP4

1. Click **YouTube** at the top of the site.
2. Copy the video's link from YouTube, then click **Paste** (or paste it into the box). Morph shows the video's title and picture.
3. Choose **Audio only** or **Video**.
4. Choose a format and quality:
   - **For music or podcasts:** MP3 at 192 kbps. YouTube's own sound is about 130–160 kbps, so 192 keeps all of it.
   - **To watch offline:** MP4 at 1080p plays on everything. 1440p and 4K also work, but they play best in a browser or VLC.
5. Click **Download**. The file goes to your Downloads folder.

![Saving a YouTube video as MP3](docs/images/youtube.png)

It also works with many other video sites. Leave **Add title, artist and cover art** switched on so your music app shows the right name and picture.

### If YouTube says "Sign in to confirm you're not a bot"

YouTube blocks many cloud computers, including Codespaces, until they prove a real person is using them. The fix is to let Morph use your YouTube sign-in. It takes about 2 minutes, and when it's needed Morph opens these steps for you:

1. Add the free **Get cookies.txt LOCALLY** extension to Chrome or Edge, or **cookies.txt** to Firefox.
2. In the extension's settings, turn on **Allow in Incognito** (Firefox: **Run in Private Windows**).
3. Open a **private window** and sign in to YouTube. A spare Google account is safest.
4. While you're on youtube.com, click the extension and **export** the cookies. A `.txt` file downloads.
5. Close the private window **without signing out**.
6. In Morph's YouTube page, click **Upload cookies.txt** and pick that file. Morph tries your video again by itself.

![The YouTube sign-in steps in Morph](docs/images/youtube-signin.png)

**Good to know**
- Morph keeps **only the YouTube cookies** from the file (it throws away any others), stores them privately, and uses them **only for your downloads**. Other people using your Morph can't use your sign-in.
- To stop using it, click **Manage sign-in → Remove my sign-in** on the YouTube page.
- The sign-in wears out after a while. If the message comes back, export a fresh file and upload it again.
- YouTube may limit accounts that download a lot, which is why a spare account is the safest choice.
- Running Morph **on your own computer** usually avoids the message completely, because home internet isn't blocked the way cloud computers are.

> Only download videos you own or have permission to save. Downloading may break a site's terms of service.

---

## PDF tools

Click **PDF tools** at the top, pick a tool, add your files, and click the button.

| Tool | What it does |
|---|---|
| **Merge PDFs** | Joins several PDFs into one. Use the ⌃ ⌄ arrows to change the order. |
| **Split PDF** | Makes one PDF per page, or splits by ranges you type, like `1-3, 4-9`. |
| **Compress PDF** | Shrinks the pictures inside a PDF so it's easier to email. Choose Light, Balanced or Strong. |
| **Rotate PDF** | Turns every page, or just the pages you list. |
| **Images → PDF** | Turns photos or scans into one PDF, fitted to each picture or to A4/Letter pages. |
| **Zip files** | Bundles any files into a single .zip. |

![Merging two PDFs](docs/images/pdf-tools.png)

---

## What it can convert

| Family | Examples |
|---|---|
| **Video** | MP4, MOV, MKV, WebM, AVI, WMV, FLV, M4V, MPEG, 3GP, TS, and video → GIF |
| **Audio** | MP3, WAV, FLAC, AAC, M4A, ALAC, OGG, Opus, WMA, AIFF, and sound from any video |
| **Images** | JPG, PNG, WebP, HEIC (iPhone photos), AVIF, GIF, TIFF, BMP, ICO, ICNS, PSD |
| **Vector** | SVG → PNG, JPG, PDF |
| **Documents** | Word (DOCX, DOC), ODT, RTF, TXT, HTML, Apple Pages → PDF and each other |
| **Spreadsheets** | Excel (XLSX, XLS), ODS, CSV, TSV, Apple Numbers |
| **Presentations** | PowerPoint (PPTX, PPT), ODP, Apple Keynote → PDF or pictures of each slide |
| **PDF** | PDF → Word, JPG/PNG/WebP/TIFF, text |
| **Markup** | Markdown, LaTeX, reStructuredText, Org, AsciiDoc, Typst, Jupyter notebooks |
| **E-books** | EPUB, MOBI, AZW3 (Kindle), FB2 and more |
| **Data** | JSON, YAML, XML, TOML, INI, PLIST, CSV, Excel, and tables as HTML, Markdown or SQL |
| **Archives** | ZIP, 7Z, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, and opening RAR |
| **Fonts** | TTF, OTF, WOFF, WOFF2 |
| **Subtitles** | SRT, VTT, ASS, LRC, TTML, SBV, and pulling subtitles out of MKV or MP4 videos |
| **Text in pictures** | PNG, JPG and other images → TXT (reads the words in a photo or screenshot) |

For the full list, click **Formats** at the top of the site. You can search it (try `heic`), and clicking any format pair opens that converter.

![The Formats page](docs/images/formats.png)

---

## Good to know

- **Your files are private.** Only you can see or download the files you convert, even if other people use the same Morph.
- **Files delete themselves** 60 minutes after converting, so download what you need.
- **Size limit:** up to 4 GB per file.
- **Up to 12 files convert at the same time** per person. Add more and they wait their turn.
- **Big videos take longer in Codespaces** because they have to upload to the cloud and download back.

### Let a friend use it

Your Morph's web address is private to your GitHub account. To share it:

1. In Codespaces, open the **Ports** tab.
2. Right-click **8080** and choose **Port Visibility → Public**.
3. Send them the address shown in the **Forwarded Address** column.

It only works while your codespace is running. Switch it back to **Private** when you're done.

---

## If something goes wrong

| Problem | What to do |
|---|---|
| **YouTube says "confirm you're not a bot"** | Follow the [sign-in steps](#if-youtube-says-sign-in-to-confirm-youre-not-a-bot). If you've already signed in and it comes back, your sign-in has worn out: export and upload a fresh cookies file. |
| **A YouTube video won't download for another reason** | YouTube changes often, so update the downloader: in the terminal running Morph, press `Ctrl` + `C`, type `pip3 install --user -U "yt-dlp[default]"`, press `Enter`, then start Morph again with `python app.py`. (Reopening the codespace also does this for you.) |
| **The Morph tab says it can't connect** | The terminal running Morph was closed. In Codespaces, open a new terminal (**☰ menu → Terminal → New Terminal**), type `python app.py`, and press `Enter`. |
| **The codespace is stuck setting up** | The first setup can take 10 minutes. If it fails, press `Ctrl` + `Shift` + `P`, type **Rebuild Container**, and press `Enter`. |
| **A format is missing from the list** | That file type can't be converted to that format. Check the **Formats** page to see what your file can become. |
| **"This file type isn't supported yet"** | Morph doesn't know that file extension. Check that the file name ends in the right extension, like `.mp4` or `.docx`. |
| **A conversion failed** | The red message under the file explains why. Most often the file is damaged or password-protected. Click ↻ to try again. |

**Restarting Morph in Codespaces:** click in the terminal that shows *Morph is running*, press `Ctrl` + `C`, then type `python app.py` and press `Enter`.

---

## Run it on your own computer

You don't need this if you use Codespaces.

**Windows**
1. Install Python from [python.org/downloads](https://www.python.org/downloads/). On the first screen of the installer, tick **"Add python.exe to PATH"**.
2. On this page, click the green **Code** button, then **Download ZIP**. Unzip it.
3. Double-click **`start-windows.bat`**. The first time takes 2–5 minutes, then your browser opens Morph.

**Mac or Linux:** download the ZIP the same way, open Terminal in the folder, and run `./start-mac-linux.sh`.

On your own computer, video, audio, images, PDF, Markdown, data, archives and fonts work straight away. For the rest, install these free helpers and then restart Morph:

| Helper | Adds | Windows (in PowerShell) | Mac (with [Homebrew](https://brew.sh)) |
|---|---|---|---|
| Deno | Reliable YouTube downloads | `winget install --id=DenoLand.Deno` | `brew install deno` |
| LibreOffice | Word, Excel, PowerPoint, Pages, Keynote | `winget install TheDocumentFoundation.LibreOffice` | `brew install --cask libreoffice` |
| Calibre | Kindle e-books | `winget install calibre.calibre` | `brew install --cask calibre` |
| Tesseract | Reading text in pictures | `winget install UB-Mannheim.TesseractOCR` | `brew install tesseract` |
| ImageMagick | SVG images | `winget install ImageMagick.ImageMagick` | `brew install librsvg` |
| 7-Zip | Opening RAR files | `winget install 7zip.7zip` | `brew install sevenzip` |

**With Docker:** `docker build -t morph .` then `docker run -p 8080:8080 morph`. The Docker image has every helper installed.

---

## For developers

Everything the website does is a plain HTTP call. The **Developers** page on the site has the full reference.

```bash
curl -F "file=@holiday.mov" -F "target=mp4" http://localhost:8080/api/convert    # → {"id": "…"}
curl http://localhost:8080/api/jobs/<id>                                         # → {"status": "done", …}
curl -OJ http://localhost:8080/api/jobs/<id>/download
```

**Project layout**

```
app.py               web server, pages and API (Flask + Waitress)
youtube.py           YouTube downloads (yt-dlp)
core/registry.py     every format, option and conversion route
core/tools.py        finds FFmpeg, LibreOffice, Pandoc, Calibre…
core/jobs.py         background jobs, progress, privacy, clean-up
converters/          media, images, documents, pdf, data, archives, fonts
static/              the website (plain HTML, CSS, JavaScript; no build step)
.devcontainer/       the GitHub Codespaces setup
tests/smoke_test.py  runs about 100 real conversions to check everything works
```

**Adding a conversion.** Write a function that takes `ctx` and returns the file it made, then register it. The website, Formats page and API pick it up automatically.

```python
from core.registry import converter

@converter(["mp4", "mov"], ["mp3"], options=["abitrate"], requires=["ffmpeg"], engine="FFmpeg")
def my_converter(ctx):
    out = ctx.out()                  # output path, named after the upload
    ...                              # read ctx.src, use ctx.opts, call ctx.progress(0.5, "Halfway…")
    return out
```

**Settings** (environment variables): `MORPH_PORT` (8080), `MORPH_MAX_UPLOAD_MB` (4096), `MORPH_KEEP_MINUTES` (60), `MORPH_MAX_ACTIVE` (12 per visitor), `MORPH_WORKERS`, `MORPH_HOST`, and `MORPH_BEHIND_PROXY=1` when hosting behind nginx or Caddy.

**YouTube sign-in for the whole server** (instead of each visitor uploading their own): `MORPH_YT_COOKIES=/path/to/cookies.txt`, or `MORPH_YT_COOKIES_FROM_BROWSER=firefox` when Morph runs on the same computer as that browser, or `MORPH_YT_PROXY=http://user:pass@host:port` to route YouTube through a proxy. Visitors' own uploaded sign-ins are stored in `~/.morph/youtube-cookies` (change it with `MORPH_COOKIE_DIR`).
