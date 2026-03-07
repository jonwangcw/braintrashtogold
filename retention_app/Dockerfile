FROM python:3.11-slim

# System dependencies required by the app
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        tesseract-ocr \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY app/ app/
COPY scripts/ scripts/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
