FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV CUDA_VISIBLE_DEVICES=""

WORKDIR /app

RUN sed -i 's|http://deb.debian.org/debian-security|https://mirrors.huaweicloud.com/debian-security|g; s|http://deb.debian.org/debian|https://mirrors.huaweicloud.com/debian|g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    --timeout 120 --retries 10 \
    && pip install -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    --trusted-host download.pytorch.org \
    --timeout 120 --retries 10

COPY app ./app
COPY main.py ./main.py
COPY config.json.example ./config.json.example

RUN mkdir -p app/data app/rag/data_index app/rag/uploads

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
