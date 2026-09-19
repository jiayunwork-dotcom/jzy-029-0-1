FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# 物性档落在容器内本地文件
ENV BL_PROFILES_FILE=/srv/data/profiles.json
RUN mkdir -p /srv/data

EXPOSE 8000

# 只起这一个进程：HTTP + 静态页面同源
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
