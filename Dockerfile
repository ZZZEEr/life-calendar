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

# 复制所有项目文件（字体必须在里面）
COPY . .

# 创建运行时目录（即使 app.py 会自动创建，这里先建好更稳妥）
RUN mkdir -p emoji_cache user_data wallpaper_history

EXPOSE 811

# 使用 Gunicorn 生产级服务器，开启 gzip 压缩，2 个 worker
CMD ["gunicorn", "--bind", "0.0.0.0:811", "--workers", "2", "--gzip", "app:app"]
