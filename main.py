import http.server
import socketserver
import json
import os
import threading
import time
import requests
import yt_dlp
import random
from datetime import datetime, timedelta
import io

# --- 1. লাইব্রেরি ইমপোর্ট (সেফটি মোড) ---
PILLOW_AVAILABLE = False
MOVIEPY_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except Exception as e:
    print(f"⚠️ Image Lib Error: {e}")

try:
    from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
    MOVIEPY_AVAILABLE = True
except Exception as e:
    print(f"⚠️ Video Lib Error: {e}")

# --- 2. কনফিগারেশন ---
PORT = int(os.environ.get("PORT", 8080))
CONFIG_FILE = "config.json"
DB_FILE = "news_db.json"
PROMO_IMAGE_FILE = "promo_image.jpg"
PROMO_VIDEO_FILE = "promo_video.mp4"
RETENTION_HOURS = 48 

FONTS = { 'bn': 'bn.ttf', 'hi': 'hn.ttf', 'en': 'en.ttf' }

# --- 3. AI KEYS ---
Z_AI_KEY = "cf5a27b9240b49b9a398094d440889e5.5RDCyrw5XLRVJEiH"
DEEP_AI_KEY = "7bc72502-db85-4dd2-9038-c3811d69ff7c"

# ==========================================
# ✂️ VIDEO ENGINE (Video Cutting)
# ==========================================
def download_and_cut_video(url):
    if not MOVIEPY_AVAILABLE:
        return False
    
    print(f"🎬 Processing: {url}")
    temp_raw = "temp_raw_video.mp4"
    
    # ক্লিনআপ
    if os.path.exists(temp_raw): os.remove(temp_raw)
    if os.path.exists(PROMO_VIDEO_FILE): os.remove(PROMO_VIDEO_FILE)

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': temp_raw,
        'quiet': True,
        'no_warnings': True,
        'overwrites': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        print("✂️ Cutting 30s...")
        ffmpeg_extract_subclip(temp_raw, 0, 30, targetname=PROMO_VIDEO_FILE)
        
        if os.path.exists(temp_raw): os.remove(temp_raw)
        return True
    except Exception as e:
        print(f"❌ Video Error: {e}")
        return False

# ==========================================
# 🩺 SYSTEM DOCTOR
# ==========================================
SERVER_START_TIME = time.time()
ERROR_LOGS = []

def get_system_report():
    uptime = str(timedelta(seconds=int(time.time() - SERVER_START_TIME)))
    
    db_count = 0
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                data = json.load(f)
                db_count = len(data.get('news', []))
        except: pass

    config = load_config()
    active_ch = sum(len(v) for v in config.get('channels', {}).values())
    vid_status = "OK" if MOVIEPY_AVAILABLE else "Missing"
    
    return f"Uptime: {uptime} | DB: {db_count} | VideoEngine: {vid_status} | Errors: {len(ERROR_LOGS)}"

# ==========================================
# 🧠 ROBOT LOGIC (Data Collection)
# ==========================================
def load_config():
    if not os.path.exists(CONFIG_FILE): return {}
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

def load_db():
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, 'r') as f: return json.load(f).get("news", [])
    except: return []

def clean_old_news(news_list):
    current_time = time.time()
    retention_seconds = RETENTION_HOURS * 3600
    cleaned = []
    for n in news_list:
        if (current_time - n.get('timestamp', 0)) < retention_seconds:
            cleaned.append(n)
    return cleaned

def fetch_social_videos(channels):
    video_news = []
    ydl_opts = {'quiet': True, 'ignoreerrors': True, 'extract_flat': True, 'playlistend': 10}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for cat, urls in channels.items():
            for url in urls:
                try:
                    info = ydl.extract_info(url, download=False)
                    entries = list(info['entries']) if 'entries' in info else [info]
                    for vid in entries:
                        if vid:
                            video_news.append({
                                "id": vid['id'], "title": vid.get('title', 'Video'),
                                "thumb": vid.get('thumbnail', ''), 
                                "original_link": vid.get('webpage_url', url),
                                "timestamp": time.time(), "platform": "yt/fb"
                            })
                except: pass
    return video_news

def robot_loop():
    print("🤖 ROBOT STARTED")
    while True:
        try:
            config = load_config()
            existing = load_db()
            fresh = fetch_social_videos(config.get("channels", {}))
            
            seen = {i['id'] for i in existing}
            for item in fresh:
                if item['id'] not in seen: existing.append(item)
            
            with open(DB_FILE, 'w') as f:
                json.dump({"news": existing, "updated": str(datetime.now())}, f)
            time.sleep(600)
        except Exception as e:
            ERROR_LOGS.append(str(e))
            time.sleep(60)

# ==========================================
# 🚀 AI ENGINE (Z-AI + DeepAI Backup)
# ==========================================
def ask_ai(prompt):
    print(f"🤖 Sending to AI: {prompt[:30]}...")
    
    # 1. Z-AI Attempt
    try:
        h = { "Authorization": f"Bearer {Z_AI_KEY}", "Content-Type": "application/json" }
        d = { "model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}], "max_tokens": 150 }
        r = requests.post("https://api.openai.com/v1/chat/completions", headers=h, json=d, timeout=30)
        if r.status_code == 200: 
            return r.json()['choices'][0]['message']['content']
    except: pass

    # 2. DeepAI Backup
    try:
        r = requests.post("https://api.deepai.org/api/text-generator", data={'text': prompt}, headers={'api-key': DEEP_AI_KEY}, timeout=30)
        if r.status_code == 200: 
            return r.json()['output']
    except: pass

    return "AI is sleeping. Check logs."

def create_thumbnail(img_url, title, lang='bn'):
    if not PILLOW_AVAILABLE: return False
    try:
        r = requests.get(img_url, timeout=10)
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img = img.resize((1280, 720))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 500), (1280, 720)], fill=(0,0,0,200))
        
        font_file = FONTS.get(lang, 'en.ttf')
        try: font = ImageFont.truetype(font_file, 50)
        except: font = ImageFont.load_default()

        draw.text((40, 550), "LPBS NEWS", fill="red", font=font)
        draw.text((40, 600), title[:60]+"...", fill="white", font=font)
        
        img.save(PROMO_IMAGE_FILE)
        return True
    except: return False

# ==========================================
# 🌐 SERVER HANDLER (All Features Included)
# ==========================================
class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        try:
            data = json.loads(self.rfile.read(length))
        except:
            data = {}

        if self.path == '/save_config':
            with open(CONFIG_FILE, 'w') as f: json.dump(data, f)
            self.send_response(200); self.end_headers(); self.wfile.write(b"Saved")

        elif self.path == '/create_promo':
            ai_text = ask_ai(f"Viral caption for: {data.get('title')}")
            create_thumbnail(data.get('thumb'), data.get('title'), data.get('lang', 'bn'))
            
            vid_ok = False
            if data.get('video_url'):
                vid_ok = download_and_cut_video(data.get('video_url'))
            
            self._send_json({
                "hashtags": ai_text,
                "image_url": f"/get_promo_image?t={int(time.time())}",
                "video_url": f"/get_promo_video?t={int(time.time())}" if vid_ok else None,
                "status": "success"
            })

        elif self.path == '/chat_with_doctor':
            msg = data.get('message', '')
            report = get_system_report()
            reply = ask_ai(f"System: {report}. User: {msg}. Reply short.")
            self._send_json({"reply": reply})
            
        elif self.path == '/publish_social':
             self._send_json({"status": "manual"})

        else: self.send_error(404)

    def do_GET(self):
        # 404 Fix
        if self.path == '/': self.path = '/index.html'

        if self.path == '/get_stats':
            if os.path.exists("stats.json"):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(open("stats.json", "rb").read())
            else:
                self.send_response(200); self.wfile.write(b'{"total":0}')
            
        elif self.path == '/check_health':
            self._send_json({"report": get_system_report()})

        elif self.path.startswith('/get_promo_image'):
            if os.path.exists(PROMO_IMAGE_FILE):
                self.send_response(200); self.send_header('Content-type', 'image/jpeg'); self.end_headers()
                self.wfile.write(open(PROMO_IMAGE_FILE, "rb").read())
            else: self.send_error(404)

        elif self.path.startswith('/get_promo_video'):
            if os.path.exists(PROMO_VIDEO_FILE):
                self.send_response(200); self.send_header('Content-type', 'video/mp4'); self.end_headers()
                self.wfile.write(open(PROMO_VIDEO_FILE, "rb").read())
            else: self.send_error(404)
            
        elif self.path == '/track_visit':
             self.update_stats(); self.send_response(200); self.end_headers()

        else: super().do_GET()

    def update_stats(self):
        s_file = "stats.json"
        data = {"total": 0, "today": 0, "date": ""}
        if os.path.exists(s_file):
            try: data = json.load(open(s_file))
            except: pass
        
        today = datetime.now().strftime("%Y-%m-%d")
        if data["date"] != today:
            data["date"] = today; data["today"] = 0
        data["total"] += 1; data["today"] += 1
        
        try: json.dump(data, open(s_file, 'w'))
        except: pass

if __name__ == "__main__":
    t = threading.Thread(target=robot_loop); t.daemon = True; t.start()
    with socketserver.TCPServer(("0.0.0.0", PORT), MyRequestHandler) as httpd:
        print(f"🔥 SERVER ON {PORT}"); httpd.serve_forever()
