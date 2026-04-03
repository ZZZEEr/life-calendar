import calendar
import datetime
import os
import io
import json
import requests
from flask import Flask, send_file, request, render_template_string, redirect, url_for
from PIL import Image, ImageDraw, ImageFont, ImageOps

app = Flask(__name__)

# ================= 🔧 基础配置 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
BG_PATH = os.path.join(BASE_DIR, "background.jpg")
CACHE_DIR = os.path.join(BASE_DIR, "emoji_cache")
# ✨ 修改：生成的壁纸缓存文件路径改为 PNG
WALLPAPER_CACHE_PATH = os.path.join(BASE_DIR, "cached_wallpaper.png")

# 自动创建缓存目录
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "color_past": "#FF7F50",
    "color_today": "#FF0000",
    "color_future": "#B4B4B4",
    "festivals": {
        "1-1": "🎆", "2-14": "🌹", "5-1": "🚩", "5-20": "❤️", 
        "10-1": "🇨🇳", "12-25": "🎄", "2-17": "🧧"
    },
    "layout": {
        "target_width": 1179,
        "target_height": 2556,
        "margin_top": 850,
        "margin_side": 110,
        "circle_radius_ratio": 0.28
    }
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
        for key, value in DEFAULT_CONFIG.items():
            if key not in config: config[key] = value
        return config

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    # ✨ 关键点：配置保存后，强制触发一次重绘
    print("⚙️ 配置已更新，正在重新生成壁纸...")
    generate_and_save_wallpaper()

def hex_to_rgba(hex_color, alpha=255):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)

def get_font(name_list, size):
    if isinstance(name_list, str): name_list = [name_list]
    for name in name_list:
        font_path = os.path.join(BASE_DIR, name)
        if os.path.exists(font_path):
            try: return ImageFont.truetype(font_path, size)
            except: continue
    return ImageFont.load_default()

# ================= 🎨 核心绘图逻辑 (只负责生成和保存) =================

def generate_and_save_wallpaper():
    """生成壁纸并保存到硬盘，不返回流"""
    try:
        cfg = load_config()
        layout = cfg['layout']
        W, H = layout['target_width'], layout['target_height']

        # 1. 加载背景
        if not os.path.exists(BG_PATH):
            bg = Image.new("RGBA", (W, H), (30, 30, 30, 255))
        else:
            try:
                bg_raw = Image.open(BG_PATH)
                bg_raw = ImageOps.exif_transpose(bg_raw) 
                bg = ImageOps.fit(bg_raw, (W, H), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
                bg = bg.convert("RGBA")
            except:
                bg = Image.new("RGBA", (W, H), (50, 50, 50, 255))

        draw = ImageDraw.Draw(bg)
        
        # 2. 字体加载
        f_title = get_font(["ARIALNB.TTF", "arialbd.ttf", "arial.ttf"], 45)
        f_emoji_fallback = get_font(["seguiemj.ttf", "AppleColorEmoji.ttf"], 60)
        # ✨ 恢复字号为 140
        f_progress = get_font(["ARIALNB.TTF", "arialbd.ttf", "arial.ttf"], 45)

        col_past = hex_to_rgba(cfg['color_past'])
        col_today = hex_to_rgba(cfg.get('color_today', '#FF0000'))
        col_future = hex_to_rgba(cfg['color_future'])

        # 强制北京时间
        tz_beijing = datetime.timezone(datetime.timedelta(hours=8))
        today_dt = datetime.datetime.now(tz_beijing)
        today = today_dt.date()
        year = today.year
        cal = calendar.Calendar(firstweekday=6)

        margin_side = layout['margin_side']
        margin_top = layout['margin_top']
        card_w = (W - 2 * margin_side) / 3
        row_spacing = 340 

        for month in range(1, 13):
            idx = month - 1
            col, row = idx % 3, idx // 3
            bx, by = margin_side + col * card_w, margin_top + row * row_spacing
            draw.text((bx + card_w/2, by), calendar.month_name[month][:3].upper(), font=f_title, fill=(255,255,255), anchor="mm")
            
            weeks = cal.monthdayscalendar(year, month)
            grid_y, cell = by + 45, card_w / 8.5 
            
            for i, week in enumerate(weeks):
                for j, day in enumerate(week):
                    if day == 0: continue
                    cx, cy = bx + (card_w - 7*cell)/2 + j*cell + cell/2, grid_y + i*cell + cell/2
                    r = cell * layout['circle_radius_ratio']
                    d_key = f"{month}-{day}"
                    cur_date = datetime.date(year, month, day)
                    
                    if d_key in cfg['festivals']:
                        emoji_char = cfg['festivals'][d_key]
                        cache_name = "".join([f"{ord(c):x}" for c in emoji_char]) + ".png"
                        cache_path = os.path.join(CACHE_DIR, cache_name)
                        
                        icon = None
                        if os.path.exists(cache_path):
                            try: icon = Image.open(cache_path).convert("RGBA")
                            except: pass
                        
                        if not icon:
                            try:
                                emoji_url = f"https://emojicdn.elk.sh/{emoji_char}?style=apple"
                                resp = requests.get(emoji_url, timeout=5)
                                if resp.status_code == 200:
                                    icon = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                                    icon.save(cache_path)
                            except: pass
                        
                        if icon:
                            icon_size = int(cell * 0.95)
                            icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                            bg.paste(icon, (int(cx - icon_size/2), int(cy - icon_size/2)), icon)
                        else:
                            draw.text((cx, cy), emoji_char, font=f_emoji_fallback, anchor="mm")
                    
                    elif cur_date == today:
                        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=col_today)
                    elif cur_date < today:
                        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=col_past)
                    else:
                        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=col_future)

        # 底部文字
        year_end = datetime.date(year, 12, 31)
        days_left = (year_end - today).days
        progress_pct = (today - datetime.date(year, 1, 1)).days / 365
        text_y = H - 400 
        draw.text((W // 2, text_y), f"{days_left} DAYS / {progress_pct:.1%}", font=f_progress, fill=(255,255,255), anchor="mm")

        # ✨ 修改：保存为 PNG 保证高清画质，并开启优化以减小体积
        bg.save(WALLPAPER_CACHE_PATH, 'PNG', optimize=True)
        print(f"✅ 高清壁纸已更新: {WALLPAPER_CACHE_PATH}")
        return True
    except Exception as e:
        print(f"❌ 生成壁纸失败: {e}")
        return False

# ================= 🌐 路由接口 =================

@app.route('/wallpaper')
def get_wallpaper():
    # 1. 检查文件是否存在
    if not os.path.exists(WALLPAPER_CACHE_PATH):
        print("⚠️ 缓存文件不存在，首次生成...")
        generate_and_save_wallpaper()
        return send_file(WALLPAPER_CACHE_PATH, mimetype='image/png')

    # 2. 检查日期是否变更 (对比文件修改时间)
    file_time = datetime.datetime.fromtimestamp(os.path.getmtime(WALLPAPER_CACHE_PATH))
    tz_beijing = datetime.timezone(datetime.timedelta(hours=8))
    now_beijing = datetime.datetime.now(tz_beijing)
    
    if file_time.date() < now_beijing.date():
        print(f"🔄 检测到日期变更，正在重新生成...")
        generate_and_save_wallpaper()
    
    # 3. 直接返回 PNG 文件
    return send_file(WALLPAPER_CACHE_PATH, mimetype='image/png')

@app.route('/upload_bg', methods=['POST'])
def api_upload_bg():
    file = request.files.get('file')
    if file:
        file.save(BG_PATH)
        generate_and_save_wallpaper()
        return "OK", 200
    return "No File", 400

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    cfg = load_config()
    if request.method == 'POST':
        if 'save_config' in request.form:
            cfg['color_past'], cfg['color_today'], cfg['color_future'] = request.form.get('color_past'), request.form.get('color_today'), request.form.get('color_future')
            dates, emojis = request.form.getlist('fest_date'), request.form.getlist('fest_emoji')
            cfg['festivals'] = {f"{datetime.datetime.strptime(d, '%Y-%m-%d').month}-{datetime.datetime.strptime(d, '%Y-%m-%d').day}": e for d, e in zip(dates, emojis) if d and e}
            save_config(cfg)
        if 'bg_file' in request.files:
            f = request.files['bg_file']
            if f.filename != '': 
                f.save(BG_PATH)
                generate_and_save_wallpaper()
        return redirect(url_for('dashboard'))

    display_festivals = []
    for k, v in cfg['festivals'].items():
        try:
            m, d = k.split('-')
            display_festivals.append({"date": f"{datetime.date.today().year}-{int(m):02d}-{int(d):02d}", "emoji": v})
        except: pass
    
    if not os.path.exists(WALLPAPER_CACHE_PATH):
        generate_and_save_wallpaper()

    return render_template_string('''
    <!doctype html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Life Calendar 控制台</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>body{background:#f4f6f9;padding-bottom:50px;}.preview-box{width:100%;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.1);overflow:hidden;}.preview-box img{width:100%;display:block;}.card{border:none;border-radius:12px;margin-bottom:20px;}</style>
    </head>
    <body>
    <div class="container mt-4">
        <h3 class="mb-4 text-center fw-bold">📅 生命日历设置</h3>
        <div class="row">
            <div class="col-md-7">
                <form method="POST" enctype="multipart/form-data">
                    <div class="card p-3">
                        <label class="fw-bold mb-2">🎨 进度颜色</label>
                        <div class="d-flex gap-2">
                            <input type="color" name="color_past" value="{{ cfg.color_past }}" class="form-control form-control-color w-100">
                            <input type="color" name="color_today" value="{{ cfg.color_today }}" class="form-control form-control-color w-100">
                            <input type="color" name="color_future" value="{{ cfg.color_future }}" class="form-control form-control-color w-100">
                        </div>
                    </div>
                    <div class="card p-3"><h5>🖼️ 更换背景图</h5><input type="file" name="bg_file" class="form-control"></div>
                    <div class="card p-3"><h5>🎉 纪念日</h5>
                        <div id="fest-list">
                            {% for item in festivals %}
                            <div class="input-group mb-2">
                                <input type="date" name="fest_date" class="form-control" value="{{ item.date }}">
                                <input type="text" name="fest_emoji" class="form-control" value="{{ item.emoji }}" style="max-width:80px;">
                                <button type="button" class="btn btn-outline-danger" onclick="this.parentElement.remove()">🗑️</button>
                            </div>
                            {% endfor %}
                        </div>
                        <button type="button" class="btn btn-sm btn-outline-primary w-100" onclick="addFest()">+ 添加</button>
                    </div>
                    <button type="submit" name="save_config" class="btn btn-primary w-100 fw-bold py-2">💾 保存并同步</button>
                </form>
            </div>
            <div class="col-md-5 mt-4 mt-md-0 text-center">
                <h5 class="fw-bold">预览 (点击查看原图)</h5>
                <div class="preview-box"><a href="/wallpaper" target="_blank"><img src="/wallpaper?t={{ ts }}"></a></div>
            </div>
        </div>
    </div>
    <script>function addFest(){const d=document.createElement('div');d.className='input-group mb-2';d.innerHTML='<input type="date" name="fest_date" class="form-control"><input type="text" name="fest_emoji" class="form-control" style="max-width:80px;"><button type="button" class="btn btn-outline-danger" onclick="this.parentElement.remove()">🗑️</button>';document.getElementById('fest-list').appendChild(d);}</script>
    </body></html>
    ''', cfg=cfg, festivals=display_festivals, ts=datetime.datetime.now().timestamp())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=811)