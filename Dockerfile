FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Install system dependencies required for docling and general utilities
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies using uv
RUN uv pip install --system -e .

# Copy source code
COPY . .

# Default command can be overridden by docker-compose
CMD ["bash"]
