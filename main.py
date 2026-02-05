import http.server
import socketserver
import json
import os
import threading
import time
import requests
import yt_dlp
import random
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import io
import textwrap

# --- ভিডিও এডিটিং লাইব্রেরি (নতুন সংযোজন) ---
try:
    from moviepy.editor import VideoFileClip
    from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("⚠️ WARNING: MoviePy library not found! Video cutting will be skipped.")

# --- ইমেজ লাইব্রেরি ---
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("⚠️ WARNING: Pillow library not found!")

# --- কনফিগারেশন ---
PORT = int(os.environ.get("PORT", 8080))
CONFIG_FILE = "config.json"
DB_FILE = "news_db.json"
PROMO_IMAGE_FILE = "promo_image.jpg"
PROMO_VIDEO_FILE = "promo_video.mp4" # কাটা ভিডিওর ফাইল
RETENTION_HOURS = 48 

FONTS = { 'bn': 'bn.ttf', 'hi': 'hn.ttf', 'en': 'en.ttf', 'tm': 'tm.ttf' }

# --- AI KEYS ---
Z_AI_KEY = "cf5a27b9240b49b9a398094d440889e5.5RDCyrw5XLRVJEiH"
DEEP_AI_KEY = "7bc72502-db85-4dd2-9038-c3811d69ff7c"

# ==========================================
# ✂️ PART 0: VIDEO CUTTING ENGINE (NEW FEATURE)
# ==========================================
def download_and_cut_video(url, duration=30):
    """ ইউটিউব/ফেসবুক থেকে ভিডিও নামিয়ে প্রথম ৩০ সেকেন্ড কাটবে """
    if not MOVIEPY_AVAILABLE: 
        print("❌ MoviePy not installed.")
        return False
    
    print(f"🎬 STARTED: Downloading video from {url}")
    temp_raw = "temp_raw_video.mp4"
    
    # আগের ফাইল পরিষ্কার করা
    if os.path.exists(temp_raw): os.remove(temp_raw)
    if os.path.exists(PROMO_VIDEO_FILE): os.remove(PROMO_VIDEO_FILE)

    # ১. ভিডিও ডাউনলোড (yt-dlp দিয়ে)
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
        
        # ২. ভিডিও কাটিং (MoviePy দিয়ে)
        print(f"✂️ Cutting first {duration} seconds...")
        # এখানে 0 থেকে duration (30) পর্যন্ত কাটা হচ্ছে
        ffmpeg_extract_subclip(temp_raw, 0, duration, targetname=PROMO_VIDEO_FILE)
        
        # টেম্প ফাইল ডিলিট
        if os.path.exists(temp_raw): os.remove(temp_raw)
        print("✅ Video Ready for Download!")
        return True
    except Exception as e:
        print(f"❌ Video Processing Error: {e}")
        return False

# ==========================================
# 🩺 PART 1: SYSTEM HELPER (AI DOCTOR)
# ==========================================
SERVER_START_TIME = time.time()
ERROR_LOGS = []

def get_system_report():
    uptime = str(timedelta(seconds=int(time.time() - SERVER_START_TIME)))
    
    db_size = 0
    news_count = 0
    if os.path.exists(DB_FILE):
        db_size = os.path.getsize(DB_FILE) / 1024 
        with open(DB_FILE, 'r') as f:
            try: news_count = len(json.load(f).get('news', []))
            except: pass

    config = load_config()
    active_channels = sum(len(v) for v in config.get('channels', {}).values())
    video_status = "Ready" if MOVIEPY_AVAILABLE else "Missing Library"

    return f"""
    - Uptime: {uptime}
    - News DB: {news_count} items ({db_size:.2f} KB)
    - Channels Monitored: {active_channels}
    - Video Engine: {video_status}
    - Recent Errors: {len(ERROR_LOGS)}
    """

# ==========================================
# 🧠 PART 2: THE ROBOT BRAIN (EXISTING)
# ==========================================

def load_config():
    if not os.path.exists(CONFIG_FILE): return {}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f: return json.load(f)

def load_db():
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f).get("news", [])
    except: return []

def clean_old_news(news_list):
    current_time = time.time()
    retention_seconds = RETENTION_HOURS * 3600
    cleaned_list = []
    for n in news_list:
        if (current_time - n.get('timestamp', 0)) < retention_seconds:
            cleaned_list.append(n)
    return cleaned_list

def get_embed_code(url, video_id):
    if "facebook.com" in url or "fb.watch" in url:
        return f"https://www.facebook.com/plugins/video.php?href={url}&show_text=0&width=560"
    elif "instagram.com" in url:
        return f"https://www.instagram.com/p/{video_id}/embed"
    else:
        return f"https://www.youtube-nocookie.com/embed/{video_id}?autoplay=0&rel=0"

def smart_mix_news(news_list, location_keyword):
    high_priority = [] 
    local_priority = [] 
    general_mix = []    
    location_keyword = location_keyword.lower()

    for item in news_list:
        title = item.get('title', '').lower()
        category = item.get('category', '').lower()
        if 'trend' in category or 'breaking' in category: high_priority.append(item)
        elif location_keyword in title: local_priority.append(item)
        else: general_mix.append(item)

    random.shuffle(general_mix)
    return high_priority + local_priority + general_mix

def fetch_google_trends():
    print("   📈 Robot: Checking Google Trends...")
    trends = []
    try:
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall('.//item')[:5]:
                title = item.find('title').text
                try: image_url = item.find('ht:picture', namespaces={'ht': 'https://trends.google.com/trends/trendingsearches/daily'}).text
                except: image_url = "https://via.placeholder.com/600x400?text=Trending"
                trends.append({
                    "id": f"trend_{abs(hash(title))}", "category": "Trending 🔥", "title": title,
                    "desc": f"Trending: {title}", "thumb": image_url, "video_url": "",
                    "timestamp": time.time(), "type": "image", "platform": "google"
                })
    except Exception as e: print(f"Trend Error: {e}")
    return trends

def fetch_social_videos(channels):
    video_news = []
    ydl_opts = { 'quiet': True, 'ignoreerrors': True, 'extract_flat': True, 'playlistend': 15 }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for category, urls in channels.items():
            print(f"   📂 Scanning {category}...")
            for url in urls:
                try:
                    info = ydl.extract_info(url, download=False)
                    entries = list(info['entries']) if 'entries' in info else [info]
                    for video in entries:
                        if not video: continue
                        vid_id = video['id']
                        thumb = video.get('thumbnail') or f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
                        video_news.append({
                            "id": vid_id, "category": category, "title": video.get('title', 'Video'),
                            "thumb": thumb, "video_url": get_embed_code(url, vid_id),
                            "original_link": video.get('webpage_url', url), 
                            "timestamp": time.time(), "platform": "yt/fb"
                        })
                except: pass
    return video_news

def robot_loop():
    print("🤖 ROBOT SYSTEM: INITIALIZED")
    while True:
        try:
            config = load_config()
            existing = clean_old_news(load_db())
            fresh = fetch_google_trends() + fetch_social_videos(config.get("channels", {}))
            
            seen_ids = {i['id'] for i in existing}
            for item in fresh:
                if item['id'] not in seen_ids: existing.append(item)
            
            optimized = smart_mix_news(existing, config.get("location_override", "India"))
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump({"news": optimized, "updated": str(datetime.now())}, f, ensure_ascii=False)
            time.sleep(300)
        except Exception as e:
            print(f"❌ ROBOT ERROR: {e}")
            ERROR_LOGS.append(str(e))
            time.sleep(60)

# ==========================================
# 🚀 PART 3: AI & PROMO ENGINE
# ==========================================

def fallback_hashtags(title):
    return f"{title}\n\n#Viral #Trending #News #Latest #FYP"

# আপনার অনুরোধে টাইমআউট বাড়িয়ে ৩০ সেকেন্ড করা হয়েছে
def ask_z_ai(prompt):
    print("🤖 Asking Z AI (Timeout: 30s)...")
    try:
        headers = { "Authorization": f"Bearer {Z_AI_KEY}", "Content-Type": "application/json" }
        payload = { "model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}], "max_tokens": 150 }
        # TIMEOUT increased to 30 seconds
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
        if response.status_code == 200: return response.json()['choices'][0]['message']['content']
    except Exception as e: print(f"⚠️ Z AI Error: {e}")
    return None

def ask_deep_ai(prompt):
    print("🤖 Asking Deep AI (Timeout: 30s)...")
    try:
        # TIMEOUT increased to 30 seconds
        response = requests.post(
            "https://api.deepai.org/api/text-generator",
            data={'text': prompt}, headers={'api-key': DEEP_AI_KEY}, timeout=30
        )
        if response.status_code == 200: return response.json()['output']
    except Exception as e: print(f"⚠️ Deep AI Error: {e}")
    return None

def generate_super_promo(title, lang):
    prompt = f"Write a viral caption with 5 hashtags for news: '{title}' in {lang}."
    res = ask_z_ai(prompt)
    if not res: res = ask_deep_ai(prompt)
    if not res: res = fallback_hashtags(title)
    return res

def create_viral_thumbnail(image_url, title, lang):
    if not PILLOW_AVAILABLE: return False
    try:
        r = requests.get(image_url, timeout=10)
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img = img.resize((1280, 720))
        draw = ImageDraw.Draw(img)
        # Dark Overlay at bottom
        draw.rectangle([(0, 500), (1280, 720)], fill=(0,0,0,200))
        try: font = ImageFont.truetype(FONTS.get(lang, 'en.ttf'), 50)
        except: font = ImageFont.load_default()
        
        draw.text((40, 520), "LPBS NEWS", fill="red", font=font)
        draw.text((40, 600), title[:60]+"...", fill="white", font=font)
        
        img.save(PROMO_IMAGE_FILE)
        return True
    except: return False

# ==========================================
# 🌐 PART 4: SERVER HANDLER (UPDATED)
# ==========================================

class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/save_config':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(data, f)
            self.send_response(200); self.wfile.write(b"Saved")
        
        elif self.path == '/create_promo':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            title = data.get('title', '')
            
            # ১. AI Hashtags & Caption
            ai_hashtags = generate_super_promo(title, data.get('lang', 'bn'))
            
            # ২. Thumbnail Generation
            create_viral_thumbnail(data.get('thumb', ''), title, data.get('lang', 'bn'))
            
            # ৩. Video Cutting (New Feature)
            video_status = False
            video_url = data.get('video_url', '')
            if video_url:
                # এখানে ৩০ সেকেন্ড সেট করা আছে, চাইলে বাড়াতে পারেন
                video_status = download_and_cut_video(video_url, duration=30)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "hashtags": ai_hashtags,
                "status": "success",
                "image_url": f"/get_promo_image?t={int(time.time())}",
                "video_url": f"/get_promo_video?t={int(time.time())}" if video_status else None
            }).encode())

        # 🔥 AI Doctor Chat
        elif self.path == '/chat_with_doctor':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            user_msg = data.get('message', '')
            
            report = get_system_report()
            full_prompt = f"System Stats: {report}. User Question: {user_msg}. Answer as a DevOps Engineer."
            
            reply = ask_z_ai(full_prompt)
            if not reply: reply = ask_deep_ai(full_prompt)
            if not reply: reply = "⚠️ Doctor is offline or busy. Please check logs manually."
            
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"reply": reply}).encode())
        
        # 🔥 Social Publish Placeholder
        elif self.path == '/publish_social':
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"status": "manual", "msg": "Token missing"}).encode())

        else: self.send_error(404)

    def do_GET(self):
        if self.path == '/track_visit':
            self.update_stats(); self.send_response(200); self.end_headers()
        
        elif self.path == '/get_stats':
            if os.path.exists("stats.json"):
                with open("stats.json", 'r') as f:
                    self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
                    self.wfile.write(f.read().encode())
            else: self.send_response(200); self.wfile.write(b'{"total":0,"today":0}')

        elif self.path == '/check_health':
            report = get_system_report()
            advice = ask_z_ai(f"Review this system status: {report}") or "System looks operational."
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"report": report, "ai_advice": advice}).encode())

        elif self.path.startswith('/get_promo_image'):
            if os.path.exists(PROMO_IMAGE_FILE):
                self.send_response(200); self.send_header('Content-type', 'image/jpeg'); self.end_headers()
                with open(PROMO_IMAGE_FILE, 'rb') as f: self.wfile.write(f.read())
            else: self.send_error(404)

        # 🔥 NEW: Video Serve Route
        elif self.path.startswith('/get_promo_video'):
            if os.path.exists(PROMO_VIDEO_FILE):
                self.send_response(200); self.send_header('Content-type', 'video/mp4'); self.end_headers()
                with open(PROMO_VIDEO_FILE, 'rb') as f: self.wfile.write(f.read())
            else: self.send_error(404)
        
        else: super().do_GET()

    def update_stats(self):
        s_file = "stats.json"
        data = {"total": 0, "today": 0, "date": ""}
        if os.path.exists(s_file):
            try:
                with open(s_file, 'r') as f: data = json.load(f)
            except: pass
        today = datetime.now().strftime("%Y-%m-%d")
        if data["date"] != today: data["date"] = today; data["today"] = 0
        data["total"] += 1; data["today"] += 1
        with open(s_file, 'w') as f: json.dump(data, f)

if __name__ == "__main__":
    robot_thread = threading.Thread(target=robot_loop)
    robot_thread.daemon = True
    robot_thread.start()
    print(f"🔥 LPBS SERVER STARTED ON PORT {PORT}")
    with socketserver.TCPServer(("0.0.0.0", PORT), MyRequestHandler) as httpd:
        httpd.serve_forever()
