# The machine GitHub Codespaces builds for Morph: Python plus every converter engine.
FROM mcr.microsoft.com/devcontainers/python:3-3.12-bookworm

RUN apt-get update \
 && export DEBIAN_FRONTEND=noninteractive \
 && apt-get install -y --no-install-recommends \
        ffmpeg \
        libreoffice-writer libreoffice-calc libreoffice-impress libreoffice-draw \
        calibre \
        tesseract-ocr \
        p7zip-full \
        librsvg2-bin poppler-utils \
        fonts-dejavu fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea fonts-noto-core \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# Deno lets yt-dlp unlock YouTube videos
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

# Calibre and LibreOffice run without a screen
ENV QT_QPA_PLATFORM=offscreen
