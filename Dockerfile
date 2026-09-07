FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DOCLING_ARTIFACTS_PATH=/root/.cache/docling/models

# System libraries for Docling (OpenCV) and the Tesseract OCR engine used by the scanned profile.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml README.md ./
RUN uv pip install --system --torch-backend cpu -e ".[dev]"

# Pre-fetch the Docling layout and table models so the first conversion does not download them.
# docker-compose.yml mounts a named volume at /root/.cache/docling; Docker seeds it from this directory.
RUN docling-tools models download layout tableformer -o /root/.cache/docling/models

COPY . .

CMD ["bash"]
