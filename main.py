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
import textwrap # [NEW] টেক্সট সুন্দরভাবে র‍্যাপ (wrap) করার জন্য

# --- 1. লাইব্রেরি ইমপোর্ট (সেফটি মোড) ---
PILLOW_AVAILABLE = False
MOVIEPY_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except Exception as e:
    print(f"⚠️ Image Module Error: {e}")

try:
    from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
    MOVIEPY_AVAILABLE = True
except Exception as e:
    print(f"⚠️ Video Module Error: {e}")

# --- 2. কনফিগারেশন ---
PORT = int(os.environ.get("PORT", 8080))
CONFIG_FILE = "config.json"
DB_FILE = "news_db.json"
PROMO_IMAGE_FILE = "promo_image.jpg"
PROMO_VIDEO_FILE = "promo_video.mp4"
RETENTION_HOURS = 48 

FONTS = { 'bn': 'bn.ttf', 'hi': 'hn.ttf', 'en': 'en.ttf' }

# [NEW] ডেটাবেস করাপশন ঠেকানোর জন্য থ্রেড লক 
FILE_LOCK = threading.Lock()

# --- 3. AI KEYS ---
SAMBANOVA_KEY = "0ad2fc42-5d7f-41c0-b923-78d71d671790"
DEEP_AI_KEY = "7bc72502-db85-4dd2-9038-c3811d69ff7c"

# ==========================================
# ✂️ VIDEO ENGINE (SPEED OPTIMIZED)
# ==========================================
def download_and_cut_video(url):
    if not MOVIEPY_AVAILABLE:
        print("❌ Video Engine Missing")
        return False
    
    print(f"🎬 Processing: {url}")
    temp_raw = "temp_raw_video.mp4"
    
    # ক্লিনআপ
    if os.path.exists(temp_raw): os.remove(temp_raw)
    if os.path.exists(PROMO_VIDEO_FILE): os.remove(PROMO_VIDEO_FILE)

    # 🔥 SPEED HACK: লো কোয়ালিটি ডাউনলোড (দ্রুত হবে)
    ydl_opts = {
        'format': 'worst[ext=mp4]', # HD এর বদলে লো কোয়ালিটি (Super Fast)
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
            with FILE_LOCK: # [FIXED] লক ব্যবহার করা হয়েছে
                with open(DB_FILE, 'r') as f:
                    data = json.load(f)
                    db_count = len(data.get('news', []))
        except: pass

    config = load_config()
    active_ch = sum(len(v) for v in config.get('channels', {}).values())
    
    vid_status = "Active ✅" if MOVIEPY_AVAILABLE else "Disabled ⚠️"
    
    return f"Uptime: {uptime} | DB: {db_count} | Video: {vid_status} | Errors: {len(ERROR_LOGS)}"

# ==========================================
# 🧠 ROBOT LOGIC
# ==========================================
def load_config():
    if not os.path.exists(CONFIG_FILE): return {}
    with FILE_LOCK: # [FIXED] লক ব্যবহার করা হয়েছে
        with open(CONFIG_FILE, 'r') as f: return json.load(f)

def load_db():
    if not os.path.exists(DB_FILE): return []
    try:
        with FILE_LOCK: # [FIXED] লক ব্যবহার করা হয়েছে
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
                            # [FIXED] বেস্ট থাম্বনেল বের করার লজিক ইম্প্রুভ করা হয়েছে
                            best_thumb = vid.get('thumbnail', '')
                            if not best_thumb and 'thumbnails' in vid and len(vid['thumbnails']) > 0:
                                best_thumb = vid['thumbnails'][-1]['url'] # শেষেরটা সাধারণত হাই কোয়ালিটি হয়
                                
                            video_news.append({
                                "id": vid['id'], "title": vid.get('title', 'Video'),
                                "thumb": best_thumb, # [FIXED]
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
            existing = clean_old_news(existing)
            fresh = fetch_social_videos(config.get("channels", {}))
            
            seen = {i['id'] for i in existing}
            for item in fresh:
                if item['id'] not in seen: existing.append(item)
            
            with FILE_LOCK: # [FIXED] লক ব্যবহার করা হয়েছে যাতে ডেটা করাপ্ট না হয়
                with open(DB_FILE, 'w') as f:
                    json.dump({"news": existing, "updated": str(datetime.now())}, f)
            time.sleep(600)
        except Exception as e:
            print(f"Robot Error: {e}")
            ERROR_LOGS.append(str(e))
            time.sleep(60)

# ==========================================
# 🚀 AI ENGINE (SambaNova + DeepAI)
# ==========================================
def ask_ai(prompt):
    print(f"🤖 User asks: {prompt[:30]}...")
    
    # 1. SambaNova
    try:
        url = "https://api.sambanova.ai/v1/chat/completions"
        headers = { "Authorization": f"Bearer {SAMBANOVA_KEY}", "Content-Type": "application/json" }
        data = {
            "model": "Meta-Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150 # [FIXED] টোকেন বাড়ানো হয়েছে যাতে বেশি হ্যাশট্যাগ আসতে পারে
        }
        r = requests.post(url, headers=headers, json=data, timeout=10)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content']
    except: pass

    # 2. DeepAI Backup
    try:
        r = requests.post(
            "https://api.deepai.org/api/text-generator",
            data={'text': prompt},
            headers={'api-key': DEEP_AI_KEY},
            timeout=15
        )
        if r.status_code == 200:
            return r.json()['output']
    except: pass

    return f"Latest Update: {prompt} #Viral #News #Trending"

def create_thumbnail(img_url, title, lang='bn'):
    if not PILLOW_AVAILABLE: return False
    try:
        # [FIXED] URL না থাকলে এরর এড়ানোর জন্য চেক
        if not img_url:
             print("⚠️ No image URL provided for thumbnail.")
             return False
             
        r = requests.get(img_url, timeout=10)
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img = img.resize((1280, 720))
        draw = ImageDraw.Draw(img)
        
        # একটু বেশি ডার্ক করা হয়েছে যাতে লেখা ভালো বোঝা যায়
        draw.rectangle([(0, 450), (1280, 720)], fill=(0,0,0,220)) 
        
        font_file = FONTS.get(lang, 'en.ttf')
        try: 
            if os.path.exists(font_file): 
                font = ImageFont.truetype(font_file, 65) # [FIXED] ফন্ট সাইজ ৫০ থেকে ৬৫ করা হয়েছে
            else: 
                print(f"⚠️ Font file {font_file} not found. Falling back to default.")
                font = ImageFont.load_default()
        except: 
            font = ImageFont.load_default()

        # [FIXED] লেখাকে আরও বোল্ড (stroke) করা হয়েছে এবং textwrap দিয়ে মাল্টি-লাইন করা হয়েছে
        draw.text((40, 480), "LPBS NEWS", fill="red", font=font, stroke_width=2, stroke_fill="white")
        
        wrapped_title = textwrap.fill(title, width=45) # লাইন ভেঙে নিচে নামানোর জন্য
        draw.text((40, 560), wrapped_title, fill="white", font=font, stroke_width=1, stroke_fill="black")
        
        img.save(PROMO_IMAGE_FILE)
        return True
    except Exception as e: 
        print(f"Thumbnail Error: {e}")
        return False

# ==========================================
# 🌐 SERVER HANDLER
# ==========================================
class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/save_config':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            with FILE_LOCK: # [FIXED]
                with open(CONFIG_FILE, 'w') as f: json.dump(data, f)
            self.send_response(200); self.end_headers(); self.wfile.write(b"Saved")

        elif self.path == '/create_promo':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            
            # [FIXED] AI প্রম্পট আপডেট করা হয়েছে যাতে অনেক বেশি ভাইরাল ট্যাগ দেয়
            ai_prompt = f"Write a catchy viral caption and generate at least 15-20 highly relevant trending hashtags for this news video title: '{data.get('title')}'. Context: News/Viral. Language: {'Bengali' if data.get('lang')=='bn' else 'English'}."
            ai_text = ask_ai(ai_prompt)
            
            create_thumbnail(data.get('thumb'), data.get('title'), data.get('lang', 'bn'))
            
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
            report = get_system_report()
            reply = ask_ai(f"System: {report}. User: {data.get('message')}. Reply short.")
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"reply": reply}).encode())
            
        elif self.path == '/publish_social':
             self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
             self.wfile.write(json.dumps({"status": "manual"}).encode())

        else: self.send_error(404)

    def do_GET(self):
        # 404 ফিক্স
        if self.path == '/':
            self.path = '/index.html'

        if self.path == '/get_stats':
            if os.path.exists("stats.json"):
                try:
                    with FILE_LOCK: # [FIXED]
                        with open("stats.json", 'r') as f:
                            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
                            self.wfile.write(f.read().encode())
                            return
                except: pass
            self.send_response(200); self.wfile.write(b'{"total":0,"today":0}')
            
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
            try: 
                with FILE_LOCK: # [FIXED]
                    with open(s_file, 'r') as f: data = json.load(f)
            except: pass
        today = datetime.now().strftime("%Y-%m-%d")
        if data["date"] != today: data["date"] = today; data["today"] = 0
        data["total"] += 1; data["today"] += 1
        try: 
            with FILE_LOCK: # [FIXED]
                with open(s_file, 'w') as f: json.dump(data, f)
        except: pass

if __name__ == "__main__":
    t = threading.Thread(target=robot_loop); t.daemon = True; t.start()
    with socketserver.TCPServer(("0.0.0.0", PORT), MyRequestHandler) as httpd:
        print(f"🔥 SERVER ON {PORT}"); httpd.serve_forever()
