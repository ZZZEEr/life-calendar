FROM python:3.12-slim
WORKDIR /app

# 安装 Pillow 需要的系统库
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libharfbuzz0b \
    libfribidi0 \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件（字体、背景图、app.py 等）
COPY . .

# 确保运行时目录存在
RUN mkdir -p emoji_cache user_data wallpaper_history

EXPOSE 520

# 生产级服务器，gzip 压缩，双 worker
CMD ["gunicorn", "--bind", "0.0.0.0:520", "--workers", "2", "--gzip", "app:app"]
