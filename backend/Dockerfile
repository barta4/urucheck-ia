FROM python:3.12-slim

# TARGETPLATFORM is provided by Docker buildx
ARG TARGETPLATFORM
ARG BUILDPLATFORM

WORKDIR /app

# Install system dependencies for dlib, face_recognition, and Pillow
# Added libjpeg-dev and zlib1g-dev for Pillow (ARM wheels sometimes need these)
# Added libopenblas-dev and liblapack-dev for dlib optimization
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libboost-dev \
    libboost-python-dev \
    libboost-filesystem-dev \
    libx11-dev \
    libglib2.0-0 \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Upgrade pip and install requirements
# On ARM, dlib will compile from source, which takes time
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/photos \
    && addgroup --system --gid 1001 appuser \
    && adduser --system --uid 1001 --ingroup appuser appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
