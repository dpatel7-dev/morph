# Morph with every converter engine pre-installed.
#   docker build -t morph .
#   docker run -p 8080:8080 morph
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libreoffice-writer libreoffice-calc libreoffice-impress libreoffice-draw \
        calibre tesseract-ocr p7zip-full librsvg2-bin poppler-utils \
        fonts-dejavu fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

# Deno lets yt-dlp unlock YouTube videos
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV MORPH_HOST=0.0.0.0 MORPH_NO_BROWSER=1 PYTHONUNBUFFERED=1 QT_QPA_PLATFORM=offscreen
EXPOSE 8080
RUN useradd --create-home morph && chown -R morph /app
USER morph
CMD ["python", "app.py"]
