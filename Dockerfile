# ---- base ----
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Tokyo

WORKDIR /app

# タイムゾーン設定に必要
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

# 依存を先に入れてキャッシュを効かせる
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体
COPY . /app

# ---- dev ----
FROM base AS dev
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
ENV LOG_LEVEL=DEBUG
CMD ["python", "main.py"]

# ---- runtime (prod) ----
FROM base AS runtime
ENV LOG_LEVEL=INFO
CMD ["python", "main.py"]
