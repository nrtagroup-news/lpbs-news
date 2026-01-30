import http.server
import socketserver
import json
import os
import threading
import time
import requests
import yt_dlp
from datetime import datetime, timedelta

# --- কনফিগারেশন ---
PORT = 8080 # Replit এই পোর্টে চলে
CONFIG_FILE = "config.json"
DB_FILE = "news_db.json"
NEWS_API_KEY = "pub_102fa773efa04ad2871534886e425eab"
RETENTION_HOURS = 48

# ==========================================
# 🧠 PART 1: THE ROBOT BRAIN (News Hunter)
# ==========================================

def load_config():
    if not os.path.exists(CONFIG_FILE): return {}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_db():
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("news", [])
    except: return []

def get_smart_date():
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    return today.strftime("%Y%m%d"), yesterday.strftime("%Y%m%d")

def clean_old_news(news_list):
    current_time = time.time()
    retention_seconds = RETENTION_HOURS * 3600
    return [n for n in news_list if (current_time - n.get('timestamp', 0)) < retention_seconds]

def fetch_text_news():
    print("   📰 Robot: Reading Newspapers...")
    articles = []
    try:
        url = f"https://newsdata.io/api/1/latest?apikey={NEWS_API_KEY}&country=in&language=bn,hi,en&image=1&removeduplicate=1"
        res = requests.get(url, timeout=10).json()
        if res.get('status') == 'success':
            for item in res.get('results', [])[:6]:
                articles.append({
                    "id": item['article_id'],
                    "category": "breaking",
                    "title": item.get('title'),
                    "desc": item.get('description') or "Click to read full story...",
                    "thumb": item.get('image_url'),
                    "source": item.get('source_id'),
                    "video_url": "",
                    "time": "Today",
                    "timestamp": time.time(),
                    "type": "image"
                })
    except: pass
    return articles

def fetch_youtube_videos(channels):
    video_news = []
    today_str, yesterday_str = get_smart_date()
    
    ydl_opts = {'quiet': True, 'ignoreerrors': True, 'extract_flat': True, 'playlistend': 5, 'socket_timeout': 10}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for category, urls in channels.items():
            print(f"   📂 Robot: Scanning {category}...")
            for url in urls:
                if not url.startswith("http"): continue
                try:
                    info = ydl.extract_info(url, download=False)
                    entries = list(info['entries']) if 'entries' in info else [info]
                    
                    found = False
                    for video in entries:
                        if not video: continue
                        v_date = video.get('upload_date')
                        is_live = video.get('live_status') == 'is_live'
                        
                        # Logic: Live > Today > Yesterday > Latest
                        tag = "Recent"
                        if is_live: tag = "🔴 LIVE"
                        elif v_date == today_str: tag = "Today"
                        elif v_date == yesterday_str: tag = "Yesterday"
                        elif not found: tag = "Latest" # Fallback
                        else: continue # Skip old videos if we already found one

                        video_news.append({
                            "id": video['id'],
                            "category": category,
                            "title": video.get('title'),
                            "desc": video.get('title'),
                            "thumb": f"https://i.ytimg.com/vi/{video['id']}/hqdefault.jpg",
                            "video_url": f"https://www.youtube-nocookie.com/embed/{video['id']}",
                            "source": info.get('uploader') or "YouTube",
                            "time": tag,
                            "timestamp": time.time(),
                            "type": "video"
                        })
                        found = True
                        break 
                except: pass
    return video_news

def robot_loop():
    print("🤖 ROBOT SYSTEM: STARTED IN BACKGROUND")
    while True:
        try:
            config = load_config()
            channels = config.get("channels", {})
            location = config.get("location_override", "India")
            
            existing_db = load_db()
            existing_db = clean_old_news(existing_db)
            
            new_text = fetch_text_news()
            new_videos = fetch_youtube_videos(channels)
            fresh = new_text + new_videos
            
            # Merge
            for item in fresh:
                if not any(ex['id'] == item['id'] for ex in existing_db):
                    existing_db.insert(0, item)
            
            # Save
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump({"news": existing_db, "updated_at": datetime.now().strftime("%I:%M %p"), "location": location}, f, indent=4, ensure_ascii=False)
            
            print(f"✅ ROBOT: Cycle Complete. Active News: {len(existing_db)}")
            print("💤 Robot sleeping for 15 minutes...")
            time.sleep(900) # প্রতি ১৫ মিনিটে একবার চেক করবে (দিনে ৯৬ বার!)
            
        except Exception as e:
            print(f"❌ ROBOT ERROR: {e}")
            time.sleep(60)

# ==========================================
# 🌐 PART 2: THE SERVER (Website Host)
# ==========================================

class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/save_config':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            self.send_response(200); self.end_headers(); self.wfile.write(b"Saved")
        else: self.send_error(404)

    def do_GET(self):
        if self.path == '/track_visit':
            self.update_stats()
            self.send_response(200); self.end_headers()
        elif self.path == '/get_stats':
            if os.path.exists("stats.json"):
                with open("stats.json", 'r') as f:
                    self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers(); self.wfile.write(f.read().encode())
            else:
                self.send_response(200); self.wfile.write(b'{"total":0,"today":0}')
        else:
            super().do_GET()

    def update_stats(self):
        s_file = "stats.json"
        data = {"total": 0, "today": 0, "date": ""}
        if os.path.exists(s_file):
            try: 
                with open(s_file, 'r') as f: data = json.load(f)
            except: pass
        
        today = datetime.now().strftime("%Y-%m-%d")
        if data["date"] != today:
            data["date"] = today; data["today"] = 0
        data["total"] += 1; data["today"] += 1
        with open(s_file, 'w') as f: json.dump(data, f)

# ==========================================
# 🚀 PART 3: LAUNCHPAD (Run Both)
# ==========================================

if __name__ == "__main__":
    # ১. রোবটকে ব্যাকগ্রাউন্ডে চালু করা
    robot_thread = threading.Thread(target=robot_loop)
    robot_thread.daemon = True
    robot_thread.start()
    
    # ২. ওয়েবসাইট সার্ভার চালু করা
    print(f"🔥 SERVER STARTED ON PORT {PORT}")
    with socketserver.TCPServer(("0.0.0.0", PORT), MyRequestHandler) as httpd:
        httpd.serve_forever()