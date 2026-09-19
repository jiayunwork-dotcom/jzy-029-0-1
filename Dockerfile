# 单镜像：FastAPI 后端 + 同进程静态前端，只暴露 HTTP 端口。
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# 依赖单独一层，利用构建缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码（含前端静态资源 app/static）；物性档目录运行时自动播种
COPY app ./app
COPY tests ./tests
COPY pytest.ini ./pytest.ini
RUN mkdir -p /srv/data

# 构建期跑测试：数学/接口不变量不过则镜像构建失败
RUN python -m pytest

ENV BL_DATA_DIR=/srv/data \
    HOST=0.0.0.0 \
    PORT=8080

EXPOSE 8080

# 容器只跑一个进程；前端由同一进程作为静态资源吐出
CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST} --port ${PORT}"]
