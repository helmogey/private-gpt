# -----------------------------------------------------------------------
# Base Image: NVIDIA CUDA 12.4.1 (Devel) on Ubuntu 22.04
# Required for compiling llama-cpp-python with CUDA support for RTX 5060/4060
# -----------------------------------------------------------------------
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS base

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# 1. Install System Dependencies & Python 3.11
# We need software-properties-common to add the deadsnakes PPA for Python 3.11
RUN apt-get update && apt-get install -y \
    software-properties-common \
    wget \
    git \
    build-essential \
    curl \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    # Install GCC-12 explicitly
    gcc-12 \
    g++-12 \
    && rm -rf /var/lib/apt/lists/*

# 2. Fix Linker Paths
# Creating symlinks for libraries in /lib64 and /usr/lib64
RUN if [ -d "/lib/x86_64-linux-gnu" ]; then \
        mkdir -p /lib64 && mkdir -p /usr/lib64 && \
        [ ! -f /lib64/libm.so.6 ] && ln -s /lib/x86_64-linux-gnu/libm.so.6 /lib64/libm.so.6 || true && \
        [ ! -f /lib64/libmvec.so.1 ] && ln -s /lib/x86_64-linux-gnu/libmvec.so.1 /lib64/libmvec.so.1 || true && \
        [ ! -f /lib64/libc.so.6 ] && ln -s /lib/x86_64-linux-gnu/libc.so.6 /lib64/libc.so.6 || true && \
        [ ! -f /usr/lib64/libc_nonshared.a ] && ln -s /usr/lib/x86_64-linux-gnu/libc_nonshared.a /usr/lib64/libc_nonshared.a || true; \
    fi

# 3. Set Compiler Environment Variables
ENV CC=/usr/bin/gcc-12
ENV CXX=/usr/bin/g++-12
ENV CUDAHOSTCXX=/usr/bin/g++-12
# Ensure NVCC is in path (Standard location for NVIDIA images)
ENV PATH="/usr/local/cuda/bin:${PATH}"

# Install Poetry
ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3.11 -

# Set Python 3.11 as the default 'python'
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Configure Poetry
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV PATH="/home/worker/app/.venv/bin:$PATH"

# CRITICAL FIX: Increase Network Timeouts for slow connections
ENV PIP_DEFAULT_TIMEOUT=600
ENV POETRY_REQUESTS_TIMEOUT=600

# -----------------------------------------------------------------------
# Dependencies Stage
# -----------------------------------------------------------------------
FROM base AS dependencies
WORKDIR /home/worker/app

COPY pyproject.toml poetry.lock ./

# Install Dependencies (including llama-index-llms-ollama)
ARG POETRY_EXTRAS="ui vector-stores-qdrant llms-ollama embeddings-ollama llms-llama-cpp"

# CRITICAL FIX: Limit parallel workers to 4 to prevent network congestion
RUN poetry config installer.max-workers 4 && \
    poetry install --no-root --extras "${POETRY_EXTRAS}" -v

# -----------------------------------------------------------------------
# CRITICAL FIX: SYNC WITH WORKING RTX5000 ENVIRONMENT
# -----------------------------------------------------------------------
# Based on the provided requirements.txt, we force install the versions
# that are known to work together. This fixes the "search attribute" error.
#
# Key upgrades from the working env:
# - qdrant-client: 1.15.1
# - llama-index-vector-stores-qdrant: 0.3.3 (Compat with new client)
# - llama-index-core: 0.11.23
# - llama-cpp-python: 0.3.16
# - sentence-transformers: 3.4.1
# - passlib: 1.7.4 (Added to fix ModuleNotFoundError)
# - pydantic/fastapi: Pinned to avoid "validation error for CreateCollection"
# -----------------------------------------------------------------------
RUN . .venv/bin/activate && \
    pip uninstall -y qdrant-client llama-index-vector-stores-qdrant && \
    pip install \
    "qdrant-client==1.15.1" \
    "llama-index-vector-stores-qdrant==0.3.3" \
    "llama-index-core==0.11.23" \
    "llama-index-llms-ollama==0.3.6" \
    "llama-index-embeddings-ollama==0.3.1" \
    "sentence-transformers==3.4.1" \
    "passlib==1.7.4" \
    "pydantic==2.11.7" \
    "pydantic-core==2.33.2" \
    "pydantic-settings==2.10.1" \
    "fastapi==0.115.6" \
    "starlette==0.41.3" \
    "uvicorn==0.35.0" \
    "fastembed" \
    --force-reinstall

# -----------------------------------------------------------------------
# Recompile llama-cpp-python with CUDA
# -----------------------------------------------------------------------
# We pin this to 0.3.16 to match your working environment
RUN . .venv/bin/activate && \
    export CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=86;89;90 -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc -DCMAKE_C_COMPILER=/usr/bin/gcc-12 -DCMAKE_CXX_COMPILER=/usr/bin/g++-12 -DCMAKE_CUDA_FLAGS='-allow-unsupported-compiler'" && \
    export FORCE_CMAKE=1 && \
    echo "Installing and Compiling llama-cpp-python==0.3.16 with CUDA support..." && \
    pip install "llama-cpp-python==0.3.16" --no-cache-dir --force-reinstall --no-deps --verbose

# -----------------------------------------------------------------------
# Final Application Stage
# -----------------------------------------------------------------------
FROM base AS app

ENV PYTHONUNBUFFERED=1
ENV PORT=8001
ENV APP_ENV=prod
ENV PYTHONPATH="$PYTHONPATH:/home/worker/app/private_gpt/"

# Create worker user
ARG UID=1000
ARG GID=1000
RUN addgroup --gid ${GID} --system worker \
    && adduser --system --gid ${GID} --uid ${UID} --home /home/worker worker

WORKDIR /home/worker/app

# Permissions
RUN chown worker /home/worker/app \
    && mkdir local_data && chown worker local_data \
    && mkdir models && chown worker models

# Copy Virtual Environment from dependencies stage
COPY --chown=worker --from=dependencies /home/worker/app/.venv/ .venv

# Copy Application Files
COPY --chown=worker private_gpt/ private_gpt
COPY --chown=worker private_gpt/ models
COPY --chown=worker *.yaml ./
COPY --chown=worker .env ./
COPY --chown=worker scripts/ scripts

# Ensure the venv is in path for the runtime
ENV PATH="/home/worker/app/.venv/bin:$PATH"

USER worker
EXPOSE 8001

ENTRYPOINT ["python", "-m", "private_gpt"]
