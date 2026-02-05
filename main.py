# ===============================
# 🔥 LPBS AI SOCIAL SERVER
# ===============================

import http.server
import socketserver
import json
import os
import threading
import time
import requests
import yt_dlp
from datetime import datetime, timedelta
import io

# ===============================
# 📦 OPTIONAL LIBS
# ===============================
PILLOW_AVAILABLE = False
MOVIEPY_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except Exception as e:
    print("⚠️ Pillow missing:", e)

try:
    from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
    MOVIEPY_AVAILABLE = True
except Exception as e:
    print("⚠️ MoviePy missing:", e)

# ===============================
# ⚙️ CONFIG
# ===============================
PORT = int(os.environ.get("PORT", 8080))
CONFIG_FILE = "config.json"
DB_FILE = "news_db.json"
PROMO_IMAGE_FILE = "promo_image.jpg"
PROMO_VIDEO_FILE = "promo_video.mp4"
RETENTION_HOURS = 48

FONTS = {
    "bn": "bn.ttf",
    "hi": "hn.ttf",
    "en": "en.ttf"
}

# ===============================
# 🔑 AI KEYS
# ===============================
Z_AI_KEY = "cf5a27b9240b49b9a398094d440889e5.5RDCyrw5XLRVJEiH"
DEEP_AI_KEY = "7bc72502-db85-4dd2-9038-c3811d69ff7c"

# ===============================
# 🎬 VIDEO ENGINE
# ===============================
def download_and_cut_video(url):
    if not MOVIEPY_AVAILABLE:
        return False

    temp_raw = "temp_raw_video.mp4"
    for f in [temp_raw, PROMO_VIDEO_FILE]:
        if os.path.exists(f):
            os.remove(f)

    try:
        with yt_dlp.YoutubeDL({
            "format": "best[ext=mp4]/best",
            "outtmpl": temp_raw,
            "quiet": True,
            "no_warnings": True
        }) as ydl:
            ydl.download([url])

        ffmpeg_extract_subclip(temp_raw, 0, 30, targetname=PROMO_VIDEO_FILE)
        os.remove(temp_raw)
        return True
    except Exception as e:
        print("🎬 Video Error:", e)
        return False

# ===============================
# 🩺 SYSTEM DOCTOR
# ===============================
SERVER_START_TIME = time.time()
ERROR_LOGS = []

def get_system_report():
    uptime = str(timedelta(seconds=int(time.time() - SERVER_START_TIME)))

    db_count = 0
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE) as f:
                db_count = len(json.load(f).get("news", []))
        except:
            pass

    return f"Uptime:{uptime} | DB:{db_count} | Video:{MOVIEPY_AVAILABLE}"

# ===============================
# 🤖 CORE LOGIC
# ===============================
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except:
        return {}

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE) as f:
            return json.load(f).get("news", [])
    except:
        return []

def clean_old_news(news):
    now = time.time()
    limit = RETENTION_HOURS * 3600
    return [n for n in news if now - n.get("timestamp", 0) < limit]

def fetch_social_videos(channels):
    results = []
    ydl_opts = {"quiet": True, "ignoreerrors": True, "extract_flat": True}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for _, urls in channels.items():
            for url in urls:
                try:
                    info = ydl.extract_info(url, download=False)
                    entries = info.get("entries") or [info]
                    for v in entries:
                        if not v:
                            continue
                        results.append({
                            "id": v.get("id"),
                            "title": v.get("title", "Video"),
                            "thumb": v.get("thumbnail", ""),
                            "original_link": v.get("webpage_url", url),
                            "timestamp": time.time(),
                            "platform": "social"
                        })
                except:
                    continue
    return results

def robot_loop():
    print("🤖 ROBOT ONLINE")
    while True:
        try:
            cfg = load_config()
            existing = clean_old_news(load_db())
            fresh = fetch_social_videos(cfg.get("channels", {}))

            seen = {n["id"] for n in existing}
            for f in fresh:
                if f["id"] not in seen:
                    existing.append(f)

            with open(DB_FILE, "w") as f:
                json.dump({"news": existing}, f)

            time.sleep(600)
        except Exception as e:
            ERROR_LOGS.append(str(e))
            time.sleep(60)

# ===============================
# 🧠 AI ENGINE (STABLE)
# ===============================
def ask_ai(prompt):
    try:
        r = requests.post(
            "https://api.deepai.org/api/text-generator",
            headers={"api-key": DEEP_AI_KEY},
            data={"text": prompt},
            timeout=15
        )
        if r.status_code == 200:
            return r.json().get("output", "")
    except Exception as e:
        ERROR_LOGS.append(str(e))

    return "AI temporarily unavailable."

# ===============================
# 🖼️ THUMBNAIL
# ===============================
def create_thumbnail(img_url, title, lang="bn"):
    if not PILLOW_AVAILABLE:
        return False
    try:
        img = Image.open(io.BytesIO(requests.get(img_url, timeout=10).content)).convert("RGB")
        img = img.resize((1280, 720))

        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 520, 1280, 720), fill=(0, 0, 0))

        font = ImageFont.truetype(FONTS.get(lang, "en.ttf"), 48)
        draw.text((40, 540), "LPBS NEWS", fill="red", font=font)
        draw.text((40, 600), title[:60], fill="white", font=font)

        img.save(PROMO_IMAGE_FILE)
        return True
    except:
        return False

# ===============================
# 🌐 SERVER
# ===============================
class MyRequestHandler(http.server.SimpleHTTPRequestHandler):

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or "{}")

        if self.path == "/create_promo":
            ai = ask_ai(f"Viral caption: {data.get('title','')}")
            create_thumbnail(data.get("thumb",""), data.get("title",""))
            video_ok = download_and_cut_video(data.get("video_url")) if data.get("video_url") else False

            self._json({
                "hashtags": ai,
                "image": "/get_promo_image",
                "video": "/get_promo_video" if video_ok else None
            })
        else:
            self.send_error(404)

    def do_GET(self):
        if self.path == "/check_health":
            self._json({"status": get_system_report()})

        elif self.path == "/get_promo_image" and os.path.exists(PROMO_IMAGE_FILE):
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            self.wfile.write(open(PROMO_IMAGE_FILE,"rb").read())
        else:
            self.send_error(404)

# ===============================
# 🚀 START
# ===============================
if __name__ == "__main__":
    threading.Thread(target=robot_loop, daemon=True).start()
    with socketserver.TCPServer(("0.0.0.0", PORT), MyRequestHandler) as srv:
        print("🔥 SERVER RUNNING ON", PORT)
        srv.serve_forever()
