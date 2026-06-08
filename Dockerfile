# syntax=docker/dockerfile:1.7
FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=600
ENV PIP_RETRIES=20
ENV CUDA_VISIBLE_DEVICES=""

WORKDIR /app

RUN sed -i 's|http://deb.debian.org/debian-security|https://mirrors.huaweicloud.com/debian-security|g; s|http://deb.debian.org/debian|https://mirrors.huaweicloud.com/debian|g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip setuptools wheel \
    -i https://repo.huaweicloud.com/repository/pypi/simple \
    --trusted-host repo.huaweicloud.com \
    --timeout 600 --retries 20 --progress-bar off

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install "torch==2.3.1+cpu" \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://repo.huaweicloud.com/repository/pypi/simple \
    --trusted-host download.pytorch.org \
    --trusted-host repo.huaweicloud.com \
    --timeout 600 --retries 20 --progress-bar off

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt \
    -i https://repo.huaweicloud.com/repository/pypi/simple \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    --trusted-host repo.huaweicloud.com \
    --trusted-host download.pytorch.org \
    --timeout 600 --retries 20 --progress-bar off

COPY app ./app
COPY main.py ./main.py
COPY config.json.example ./config.json.example

RUN mkdir -p app/data app/rag/data_index app/rag/uploads

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
