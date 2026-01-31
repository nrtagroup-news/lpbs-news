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

# --- ম্যাজিক লাইব্রেরি (Pillow) ---
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("⚠️ WARNING: Pillow library not found! requirements.txt এ Pillow যুক্ত করুন।")

# --- কনফিগারেশন (Render Port Fix) ---
# রেন্ডার অটোমেটিক যে পোর্ট দেবে সেটা নেবে, না পেলে 8080
PORT = int(os.environ.get("PORT", 8080))

CONFIG_FILE = "config.json"
DB_FILE = "news_db.json"
NEWS_API_KEY = "pub_102fa773efa04ad2871534886e425eab"
RETENTION_HOURS = 3
PROMO_IMAGE_FILE = "promo_image.jpg"

# ফন্ট ম্যাপ (আপনার ফাইলের নামের সাথে মিল রেখে)
FONTS = {
    'bn': 'bn.ttf',
    'hi': 'hn.ttf',  # আপনার আপলোড করা হিন্দি ফন্ট
    'en': 'en.ttf',
    'tm': 'tm.ttf'
}

# ==========================================
# 🧠 PART 1: THE ROBOT BRAIN
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

def get_embed_code(url, video_id):
    if "facebook.com" in url or "fb.watch" in url:
        return f"https://www.facebook.com/plugins/video.php?href={url}&show_text=0&width=560"
    elif "instagram.com" in url:
        return f"https://www.instagram.com/p/{video_id}/embed"
    else:
        return f"https://www.youtube-nocookie.com/embed/{video_id}?autoplay=0&rel=0"

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
                    "type": "image",
                    "platform": "news"
                })
    except: pass
    return articles

def fetch_social_videos(channels):
    video_news = []
    today_str, yesterday_str = get_smart_date()
    ydl_opts = {'quiet': True, 'ignoreerrors': True, 'extract_flat': True, 'playlistend': 5, 'socket_timeout': 15}

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
                        duration = video.get('duration', 0)
                        is_short = (duration > 0 and duration < 60)
                        video_id = video['id']
                        original_url = video.get('webpage_url', url)
                        embed_link = get_embed_code(original_url, video_id)
                        thumb = video.get('thumbnail')
                        if not thumb: thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                        video_news.append({
                            "id": video_id,
                            "category": category,
                            "title": video.get('title'),
                            "desc": video.get('title'),
                            "thumb": thumb,
                            "video_url": embed_link,
                            "original_link": original_url,
                            "source": info.get('uploader') or "Social Media",
                            "time": "Latest",
                            "timestamp": time.time(),
                            "type": "video",
                            "is_short": is_short,
                            "platform": "facebook" if "facebook" in original_url else "youtube"
                        })
                        found = True
                        if found: break 
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
            new_videos = fetch_social_videos(channels)
            fresh = new_text + new_videos
            for item in fresh:
                if not any(ex['id'] == item['id'] for ex in existing_db):
                    existing_db.insert(0, item)
            
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump({"news": existing_db, "updated_at": datetime.now().strftime("%I:%M %p"), "location": location}, f, indent=4, ensure_ascii=False)
            
            print(f"✅ ROBOT: Cycle Complete. Active News: {len(existing_db)}")
            time.sleep(900)
        except Exception as e:
            print(f"❌ ROBOT ERROR: {e}")
            time.sleep(60)

# ==========================================
# 🎨 PART 2: PROMO GENERATOR (Updated with Logo & Bold Text)
# ==========================================

def get_hashtags(title, lang):
    tags = ["#LPBSNews", "#Breaking"]
    title_lower = title.lower()
    keywords = {"bangladesh": "#Bangladesh", "india": "#India", "politics": "#Politics", "cricket": "#Cricket", "viral": "#Viral"}
    for key, tag in keywords.items():
        if key in title_lower: tags.append(tag)
    return " ".join(tags)

def create_viral_thumbnail(image_url, title, lang):
    if not PILLOW_AVAILABLE: return False
    try:
        response = requests.get(image_url)
        img = Image.open(io.BytesIO(response.content)).convert("RGB")
        base_width, base_height = 1280, 720
        canvas = Image.new("RGB", (base_width, base_height), (0,0,0))
        
        # ইমেজ সাইজ হ্যান্ডলিং
        img_ratio = img.width / img.height
        target_ratio = base_width / base_height
        
        if img_ratio < target_ratio: 
            new_height = base_height
            new_width = int(new_height * img_ratio)
            img_resized = img.resize((new_width, new_height))
            bg_blur = img.resize((base_width, base_height)).filter(ImageFilter.GaussianBlur(radius=30))
            canvas.paste(bg_blur, (0,0))
            canvas.paste(img_resized, ((base_width - new_width) // 2, 0))
            final_img = canvas
        else:
            final_img = img.resize((base_width, base_height))

        draw = ImageDraw.Draw(final_img)
        font_filename = FONTS.get(lang, 'en.ttf')
        
        # ফন্ট লোডিং (বড় সাইজ)
        try:
            if os.path.exists(font_filename):
                title_font = ImageFont.truetype(font_filename, 70) # ফন্ট সাইজ বড় (৭০)
                sub_font = ImageFont.truetype(font_filename, 45)   # সাবটাইটেল (৪৫)
                logo_font = ImageFont.truetype(font_filename, 40)  # লোগো ফন্ট
            else:
                title_font = ImageFont.load_default()
                sub_font = ImageFont.load_default()
                logo_font = ImageFont.load_default()
        except:
            title_font = ImageFont.load_default(); sub_font = ImageFont.load_default(); logo_font = ImageFont.load_default()

        # কালো শেড বা ওভারলে
        overlay = Image.new('RGBA', final_img.size, (0,0,0,0))
        draw_overlay = ImageDraw.Draw(overlay)
        draw_overlay.rectangle([(0, 480), (1280, 720)], fill=(0, 0, 0, 180)) 
        final_img = Image.alpha_composite(final_img.convert('RGBA'), overlay).convert('RGB')
        draw = ImageDraw.Draw(final_img)

        # 1. লোগো বসানো (Top Left)
        draw.rectangle([(30, 30), (280, 90)], fill="#cc0000") # লাল বক্স
        draw.text((45, 40), "LPBS NEWS", font=logo_font, fill="white", stroke_width=2, stroke_fill="black")

        # 2. টাইটেল (বড় + বোল্ড + স্ট্রোক)
        short_title = title[:60] + "..." if len(title) > 60 else title
        # stroke_width=4 দিয়ে লেখা বোল্ড ও আউটলাইন
        draw.text((30, 500), short_title, font=title_font, fill=(255, 255, 0), stroke_width=4, stroke_fill="black") 
        
        # 3. সাবটাইটেল (স্ট্রোক সহ)
        if lang == 'bn': subtitle = "▶ সম্পূর্ণ ভিডিও দেখতে প্রথম কমেন্টের লিঙ্কে ক্লিক করুন। 👇"
        elif lang == 'hi': subtitle = "▶ पूरा वीडियो देखने के लिए पहले कमेंट लिंक पर क्लिक करें 👇"
        else: subtitle = "▶ Watch Full Video (FULL VIDEO CLICK FIRST COMENT URL) 👇"
        
        draw.text((30, 610), subtitle, font=sub_font, fill=(255, 255, 255), stroke_width=3, stroke_fill="black")

        final_img.save(PROMO_IMAGE_FILE)
        return True
    except Exception as e:
        print(f"Thumbnail Error: {e}")
        return False

# ==========================================
# 🌐 PART 3: THE SERVER
# ==========================================

class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/save_config':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            self.send_response(200); self.end_headers(); self.wfile.write(b"Saved")
        
        elif self.path == '/create_promo':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            title = data.get('title', '')
            thumb_url = data.get('thumb', '')
            lang = data.get('lang', 'bn')
            
            hashtags = get_hashtags(title, lang)
            thumb_success = create_viral_thumbnail(thumb_url, title, lang)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "hashtags": hashtags, 
                "status": "success" if thumb_success else "error", 
                "image_url": f"/get_promo_image?t={int(time.time())}"
            }).encode())
        else:
            self.send_error(404)

    def do_GET(self):
        if self.path == '/track_visit':
            self.update_stats()
            self.send_response(200); self.end_headers()
        elif self.path == '/get_stats':
            if os.path.exists("stats.json"):
                with open("stats.json", 'r') as f:
                    self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
                    self.wfile.write(f.read().encode())
            else:
                self.send_response(200); self.wfile.write(b'{"total":0,"today":0}')
        elif self.path.startswith('/get_promo_image'):
            if os.path.exists(PROMO_IMAGE_FILE):
                self.send_response(200); self.send_header('Content-type', 'image/jpeg'); self.end_headers()
                with open(PROMO_IMAGE_FILE, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
        else:
            super().do_GET()

    # --- Syntax Error ফিক্স করা হয়েছে (আগে এক লাইনে ছিল) ---
    def update_stats(self):
        s_file = "stats.json"
        data = {"total": 0, "today": 0, "date": ""}
        if os.path.exists(s_file):
            try:
                with open(s_file, 'r') as f:
                    data = json.load(f)
            except:
                pass
        
        today = datetime.now().strftime("%Y-%m-%d")
        if data["date"] != today: data["date"] = today; data["today"] = 0
        data["total"] += 1; data["today"] += 1
        with open(s_file, 'w') as f: json.dump(data, f)

if __name__ == "__main__":
    robot_thread = threading.Thread(target=robot_loop)
    robot_thread.daemon = True
    robot_thread.start()
    print(f"🔥 SERVER STARTED ON PORT {PORT}")
    with socketserver.TCPServer(("0.0.0.0", PORT), MyRequestHandler) as httpd:
        httpd.serve_forever()


