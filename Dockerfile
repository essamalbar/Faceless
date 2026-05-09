# Multi-arch image for the faceless backend (linux/amd64 + linux/arm64).
#
# Build (single arch for local test):
#   docker build -t faceless:latest .
#
# Build (multi-arch, push to registry):
#   docker buildx build --platform linux/amd64,linux/arm64 \
#     -t ghcr.io/<you>/faceless:latest --push .
#
# Run:
#   docker compose up
FROM python:3.11-slim

# System deps:
#   ffmpeg          — assemble + faststart re-mux + ffprobe (in the same package)
#   git             — uv sometimes pulls VCS deps
#   ca-certificates — HTTPS to Anthropic / Kie / Cloudflare
#   curl            — used by the compose healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (matches the dev workflow; faster than pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy lockfiles first — dep-install layer is cached when only source changes
COPY pyproject.toml uv.lock ./

# Install only production deps (no dev extras like pytest).
#
# UV_TORCH_BACKEND=cpu tells uv to pull torch from PyTorch's CPU-only wheel
# index instead of the default PyPI wheel that bundles ~5GB of NVIDIA CUDA
# libraries. Cloud Run has no GPU — shipping CUDA wastes build time, image
# size, and cold-start latency. Affects ONLY this Docker build; the local
# Mac dev environment keeps its default (MPS-accelerated) torch via uv sync
# without this env var.
#
# We drop --frozen because UV_TORCH_BACKEND requires re-resolving the torch
# package source. The lockfile still pins everything else; the resolution
# delta is just torch's wheel URL.
ENV UV_TORCH_BACKEND=cpu
RUN uv sync --frozen --no-dev

# Copy application source
COPY pipeline/ ./pipeline/
COPY run.py ./
COPY config.yaml ./
COPY assets/ ./assets/

# Whisper model cache — mounted as a named volume so models survive restarts
# and don't inflate the image. The pipeline respects this env var; if not set
# it falls back to ~/.cache/whisper inside the container (also fine).
ENV WHISPER_CACHE_DIR=/cache/whisper

# Tell the pipeline where to write run artifacts (overridable via .env)
ENV FACELESS_OUT_ROOT=/app/out

# Run as non-root for safety
RUN useradd --create-home --shell /bin/bash app && \
    mkdir -p /app/out /cache/whisper && \
    chown -R app:app /app /cache
USER app

EXPOSE 8000

# Entrypoint script — switches between api and worker mode based on
# FACELESS_CONTAINER_MODE (default: api, for back-compat with docker compose up).
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
USER root
RUN chmod +x /usr/local/bin/entrypoint.sh
USER app
ENV FACELESS_CONTAINER_MODE=api
CMD ["/usr/local/bin/entrypoint.sh"]
