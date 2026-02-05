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

# --- 1. সেফটি ইমপোর্ট (যাতে সার্ভার ক্র্যাশ না করে) ---
PILLOW_AVAILABLE = False
MOVIEPY_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except Exception as e:
    print(f"⚠️ Image Module Error: {e}")

try:
    # ভিডিও এডিটিং লাইব্রেরি লোড করার চেষ্টা
    from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
    MOVIEPY_AVAILABLE = True
except Exception as e:
    print(f"⚠️ Video Module Error (Site will still run): {e}")

# --- 2. কনফিগারেশন ---
PORT = int(os.environ.get("PORT", 8080))
CONFIG_FILE = "config.json"
DB_FILE = "news_db.json"
PROMO_IMAGE_FILE = "promo_image.jpg"
PROMO_VIDEO_FILE = "promo_video.mp4"
RETENTION_HOURS = 48 

FONTS = { 'bn': 'bn.ttf', 'hi': 'hn.ttf', 'en': 'en.ttf' }

# --- 3. AI KEYS ---
Sambanova_AI_KEY = "0ad2fc42-5d7f-41c0-b923-78d71d671790"
Z_AI_KEY = "cf5a27b9240b49b9a398094d440889e5.5RDCyrw5XLRVJEiH"
DEEP_AI_KEY = "7bc72502-db85-4dd2-9038-c3811d69ff7c"

# ==========================================
# ✂️ VIDEO ENGINE (ক্র্যাশ প্রুফ)
# ==========================================
def download_and_cut_video(url):
    if not MOVIEPY_AVAILABLE:
        print("❌ Video engine inactive.")
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
        # ডাউনলোড
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # কাটিং (৩০ সেকেন্ড)
        ffmpeg_extract_subclip(temp_raw, 0, 30, targetname=PROMO_VIDEO_FILE)
        
        if os.path.exists(temp_raw): os.remove(temp_raw)
        return True
    except Exception as e:
        print(f"❌ Video Process Failed: {e}")
        return False

# ==========================================
# 🧠 ROBOT & SYSTEM
# ==========================================
def get_system_report():
    uptime = str(timedelta(seconds=int(time.time() - SERVER_START_TIME)))
    vid_status = "Active ✅" if MOVIEPY_AVAILABLE else "Disabled (Lib Missing) ⚠️"
    return f"Uptime: {uptime} | Video Engine: {vid_status}"

def load_config():
    if not os.path.exists(CONFIG_FILE): return {}
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

def load_db():
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, 'r') as f: return json.load(f).get("news", [])
    except: return []

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
            print(f"Robot Error: {e}")
            time.sleep(60)

# ==========================================
# 🚀 AI ENGINE (TIMEOUT FIXED 30s)
# ==========================================
def ask_ai(prompt):
    print("🤖 Asking AI...")
    try:
        # Z-AI First
        h = { "Authorization": f"Bearer {Z_AI_KEY}", "Content-Type": "application/json" }
        d = { "model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}], "max_tokens": 150 }
        r = requests.post("https://api.openai.com/v1/chat/completions", headers=h, json=d, timeout=30)
        if r.status_code == 200: return r.json()['choices'][0]['message']['content']
    except: pass
    
    try:
        # DeepAI Backup
        r = requests.post("https://api.deepai.org/api/text-generator", data={'text': prompt}, headers={'api-key': DEEP_AI_KEY}, timeout=30)
        if r.status_code == 200: return r.json()['output']
    except: pass
    
    return f"{prompt} #Viral #News"

def create_thumbnail(img_url, title):
    if not PILLOW_AVAILABLE: return False
    try:
        r = requests.get(img_url, timeout=10)
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img.save(PROMO_IMAGE_FILE)
        return True
    except: return False

# ==========================================
# 🌐 SERVER HANDLER
# ==========================================
class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/save_config':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            with open(CONFIG_FILE, 'w') as f: json.dump(data, f)
            self.send_response(200); self.wfile.write(b"Saved")

        elif self.path == '/create_promo':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            
            ai_text = ask_ai(f"Viral caption for: {data.get('title')}")
            create_thumbnail(data.get('thumb'), data.get('title'))
            
            vid_ok = False
            if data.get('video_url'):
                vid_ok = download_and_cut_video(data.get('video_url'))
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "hashtags": ai_text,
                "image_url": f"/get_promo_image?t={int(time.time())}",
                "video_url": f"/get_promo_video?t={int(time.time())}" if vid_ok else None,
                "status": "success"
            }).encode())

        elif self.path == '/chat_with_doctor':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            reply = ask_ai(f"System: {get_system_report()}. User: {data.get('message')}")
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"reply": reply}).encode())
            
        elif self.path == '/publish_social':
             self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
             self.wfile.write(json.dumps({"status": "manual"}).encode())

        else: self.send_error(404)

    def do_GET(self):
        if self.path == '/get_stats':
            if os.path.exists("stats.json"):
                with open("stats.json", 'r') as f:
                    self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
                    self.wfile.write(f.read().encode())
            else: self.send_response(200); self.wfile.write(b'{"total":0,"today":0}')
            
        elif self.path == '/check_health':
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"report": get_system_report(), "ai_advice": "Check Logs"}).encode())

        elif self.path.startswith('/get_promo_image'):
            if os.path.exists(PROMO_IMAGE_FILE):
                self.send_response(200); self.send_header('Content-type', 'image/jpeg'); self.end_headers()
                with open(PROMO_IMAGE_FILE, 'rb') as f: self.wfile.write(f.read())
            else: self.send_error(404)

        elif self.path.startswith('/get_promo_video'):
            if os.path.exists(PROMO_VIDEO_FILE):
                self.send_response(200); self.send_header('Content-type', 'video/mp4'); self.end_headers()
                with open(PROMO_VIDEO_FILE, 'rb') as f: self.wfile.write(f.read())
            else: self.send_error(404)
            
        elif self.path == '/track_visit':
             self.update_stats(); self.send_response(200); self.end_headers()

        else: super().do_GET()

    def update_stats(self):
        s_file = "stats.json"
        data = {"total": 0, "today": 0, "date": ""}
        if os.path.exists(s_file):
            try: with open(s_file, 'r') as f: data = json.load(f)
            except: pass
        today = datetime.now().strftime("%Y-%m-%d")
        if data["date"] != today: data["date"] = today; data["today"] = 0
        data["total"] += 1; data["today"] += 1
        with open(s_file, 'w') as f: json.dump(data, f)

SERVER_START_TIME = time.time()
if __name__ == "__main__":
    t = threading.Thread(target=robot_loop); t.daemon = True; t.start()
    with socketserver.TCPServer(("0.0.0.0", PORT), MyRequestHandler) as httpd:
        print(f"🔥 SERVER ON {PORT}"); httpd.serve_forever()

