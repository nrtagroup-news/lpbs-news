import http.server
import socketserver
import json
import os
import threading
import time
import requests
import yt_dlp
import random
import xml.etree.ElementTree as ET  # গুগল ট্রেন্ডস পড়ার জন্য
from datetime import datetime, timedelta
import io
import textwrap  # থাম্বনেইলের লেখা সুন্দর করার জন্য

# --- ম্যাজিক লাইব্রেরি (Pillow) ---
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("⚠️ WARNING: Pillow library not found! requirements.txt এ Pillow যুক্ত করুন।")

# --- কনফিগারেশন ---
PORT = int(os.environ.get("PORT", 8080))
CONFIG_FILE = "config.json"
DB_FILE = "news_db.json"
# নিউজ এপিআই ব্যাকআপের জন্য রাখা হলো, তবে আমরা গুগল ট্রেন্ডস বেশি ব্যবহার করব
NEWS_API_KEY = "pub_102fa773efa04ad2871534886e425eab" 
PROMO_IMAGE_FILE = "promo_image.jpg"

# 🔥 আপডেট ১: রিটেনশন ৪৮ ঘণ্টা (২ দিন) করা হয়েছে
RETENTION_HOURS = 48 

FONTS = {
    'bn': 'bn.ttf',
    'hi': 'hn.ttf',
    'en': 'en.ttf',
    'tm': 'tm.ttf'
}

# ==========================================
# 🧠 PART 1: THE ROBOT BRAIN (INTELLIGENCE)
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

# 🔥 আপডেট ২: লজিক ফিক্স - প্রতিটি খবরের বয়স আলাদাভাবে চেক হবে
def clean_old_news(news_list):
    current_time = time.time()
    retention_seconds = RETENTION_HOURS * 3600
    cleaned_list = []
    for n in news_list:
        news_age = current_time - n.get('timestamp', 0)
        # যদি খবরের বয়স ৪৮ ঘণ্টার কম হয়, তবেই সেটা রাখা হবে
        if news_age < retention_seconds:
            cleaned_list.append(n)
    return cleaned_list

def get_embed_code(url, video_id):
    if "facebook.com" in url or "fb.watch" in url:
        return f"https://www.facebook.com/plugins/video.php?href={url}&show_text=0&width=560"
    elif "instagram.com" in url:
        return f"https://www.instagram.com/p/{video_id}/embed"
    else:
        return f"https://www.youtube-nocookie.com/embed/{video_id}?autoplay=0&rel=0"

# 🔥 আপডেট ৩: Google Trending Topics (Real-time)
def fetch_google_trends():
    print("   📈 Robot: Checking Google Trends...")
    trends = []
    try:
        # ভারতের জন্য গুগল ডেইলি ট্রেন্ডস আরএসএস
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall('.//item')[:5]: # টপ ৫ ট্রেন্ড
                title = item.find('title').text
                # ডেসক্রিপশন ক্লিন করা
                desc = f"Trending now in India: {title}. See full coverage on LPBS News."
                try:
                    news_item_title = item.find('ht:news_item_title', namespaces={'ht': 'https://trends.google.com/trends/trendingsearches/daily'}).text
                    desc = news_item_title
                except: pass
                
                image_url = "https://via.placeholder.com/600x400?text=Trending+News" # ফলব্যাক ইমেজ
                try:
                    image_url = item.find('ht:picture', namespaces={'ht': 'https://trends.google.com/trends/trendingsearches/daily'}).text
                except: pass

                trends.append({
                    "id": f"trend_{abs(hash(title))}",
                    "category": "Trending 🔥",
                    "title": title,
                    "desc": desc,
                    "thumb": image_url,
                    "source": "Google Trends",
                    "video_url": "",
                    "time": "Hot Topic",
                    "timestamp": time.time(),
                    "type": "image",
                    "platform": "google"
                })
    except Exception as e:
        print(f"Trend Error: {e}")
    return trends

def fetch_social_videos(channels):
    video_news = []
    
    # 🔥 আপডেট ৪: playlistend বাড়িয়ে 15 করা হয়েছে যাতে সকালের ভিডিও মিস না হয়
    ydl_opts = {
        'quiet': True, 
        'ignoreerrors': True, 
        'extract_flat': True,
        'playlistend': 15, # আগে ৫ ছিল, এখন ১৫ করা হলো
        'socket_timeout': 20
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for category, urls in channels.items():
            print(f"   📂 Robot: Deep Scanning {category}...")
            for url in urls:
                if not url.startswith("http"): continue
                try:
                    info = ydl.extract_info(url, download=False)
                    entries = list(info['entries']) if 'entries' in info else [info]
                    
                    for video in entries:
                        if not video: continue
                        
                        video_id = video['id']
                        original_url = video.get('webpage_url', url)
                        embed_link = get_embed_code(original_url, video_id)
                        
                        thumb = video.get('thumbnail')
                        if not thumb: thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                        video_news.append({
                            "id": video_id,
                            "category": category,
                            "title": video.get('title') or "Latest Update",
                            "desc": video.get('title') or "Click to watch",
                            "thumb": thumb,
                            "video_url": embed_link,
                            "original_link": original_url,
                            "source": info.get('uploader') or "Social Media",
                            "time": "Just Now",
                            "timestamp": time.time(), # এখানে বর্তমান সময় দিচ্ছি, কিন্তু এটি ডাটাবেসে থাকলে আপডেট হবে না
                            "type": "video",
                            "platform": "facebook" if "facebook" in original_url else "youtube"
                        })
                except: pass
                # ইউটিউব ব্লক এড়াতে ছোট বিরতি
                time.sleep(2) 
    return video_news

def robot_loop():
    print("🤖 ROBOT SYSTEM: INITIALIZED & POWERFUL")
    while True:
        try:
            config = load_config()
            channels = config.get("channels", {})
            location = config.get("location_override", "India")
            
            # ১. আগের ডাটা লোড
            existing_db = load_db()
            
            # ২. পুরনো খবর ডিলিট (৪৮ ঘণ্টার বেশি হলে)
            existing_db = clean_old_news(existing_db)
            
            # ৩. নতুন খবর আনা (Google Trends + YouTube)
            new_trends = fetch_google_trends()
            new_videos = fetch_social_videos(channels)
            
            fresh_content = new_trends + new_videos
            
            # ৪. ডুপ্লিকেট চেক এবং মার্জ করা
            # নতুন কন্টেন্ট যদি ইতিমধ্যে থাকে, সেটা স্কিপ করব
            existing_ids = {item['id'] for item in existing_db}
            
            added_count = 0
            for item in fresh_content:
                if item['id'] not in existing_ids:
                    existing_db.insert(0, item) # নতুন খবর সবার উপরে
                    added_count += 1
            
            # ৫. ডাটাবেস সেভ
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "news": existing_db, 
                    "updated_at": datetime.now().strftime("%I:%M %p"), 
                    "location": location,
                    "total_articles": len(existing_db)
                }, f, indent=4, ensure_ascii=False)
            
            print(f"✅ ROBOT: Cycle Complete. New Items: {added_count}. Active News: {len(existing_db)}")
            
            # 🔥 আপডেট ৫: ফ্রিকোয়েন্সি
            # রোবট এখন প্রতি ৫ মিনিট (৩০০ সেকেন্ড) পর পর চেক করবে। 
            # ১৫ সেকেন্ড দিলে ইউটিউব আইপি ব্লক করে দেবে, তাই ৩০০ সেকেন্ড নিরাপদ এবং যথেষ্ট ফাস্ট।
            time.sleep(300) 

        except Exception as e:
            print(f"❌ ROBOT ERROR: {e}")
            time.sleep(60)

# ==========================================
# 🎨 PART 2: SMART PROMO & THUMBNAIL
# ==========================================

# 🔥 আপডেট ৬: স্মার্ট হ্যাশট্যাগ জেনারেটর
def get_hashtags(title, lang):
    title_lower = title.lower()
    tags = ["#LPBSNews", "#Latest"]
    
    # কিওয়ার্ড ম্যাপিং
    keywords = {
        "bangladesh": "#Bangladesh", "india": "#India", "modi": "#PMModi",
        "mamata": "#MamataBanerjee", "cricket": "#Cricket", "football": "#Sports",
        "viral": "#ViralVideo", "accident": "#Breaking", "election": "#Election2026",
        "budget": "#Budget", "weather": "#WeatherUpdate", "job": "#Jobs"
    }
    
    for key, tag in keywords.items():
        if key in title_lower:
            tags.append(tag)
            
    # যদি গুগল ট্রেন্ডস থেকে কিছু পাওয়া যায় (সিমুলেশন)
    tags.append("#TrendingNow")
    
    return " ".join(tags[:6]) # সর্বোচ্চ ৬টি ট্যাগ

def create_viral_thumbnail(image_url, title, lang):
    if not PILLOW_AVAILABLE: return False
    try:
        response = requests.get(image_url, timeout=5)
        img = Image.open(io.BytesIO(response.content)).convert("RGB")
        base_width, base_height = 1280, 720
        canvas = Image.new("RGB", (base_width, base_height), (0,0,0))
        
        # ইমেজ স্কেলিং এবং ব্লার ব্যাকগ্রাউন্ড
        img_ratio = img.width / img.height
        target_ratio = base_width / base_height
        
        if img_ratio < target_ratio: 
            new_height = base_height
            new_width = int(new_height * img_ratio)
            img_resized = img.resize((new_width, new_height))
            bg_blur = img.resize((base_width, base_height)).filter(ImageFilter.GaussianBlur(radius=40))
            canvas.paste(bg_blur, (0,0))
            canvas.paste(img_resized, ((base_width - new_width) // 2, 0))
            final_img = canvas
        else:
            final_img = img.resize((base_width, base_height))

        # ওভারলে (নিচের দিকে কালো শেড)
        overlay = Image.new('RGBA', final_img.size, (0,0,0,0))
        draw_overlay = ImageDraw.Draw(overlay)
        # শেড এখন একটু বড় করা হয়েছে যাতে ২ লাইনের লেখা ধরে
        draw_overlay.rectangle([(0, 450), (1280, 720)], fill=(0, 0, 0, 200)) 
        final_img = Image.alpha_composite(final_img.convert('RGBA'), overlay).convert('RGB')
        draw = ImageDraw.Draw(final_img)

        # ফন্ট লোডিং
        font_filename = FONTS.get(lang, 'en.ttf')
        try:
            # ফন্ট সাইজ একটু ছোট করা হয়েছে যাতে লাইন ব্রেক করা যায়
            if os.path.exists(font_filename):
                title_font = ImageFont.truetype(font_filename, 60)
                sub_font = ImageFont.truetype(font_filename, 40)
                logo_font = ImageFont.truetype(font_filename, 35)
            else:
                title_font = ImageFont.load_default()
                sub_font = ImageFont.load_default()
                logo_font = ImageFont.load_default()
        except:
            title_font = ImageFont.load_default(); sub_font = ImageFont.load_default(); logo_font = ImageFont.load_default()

        # লোগো (উপরে বামে)
        draw.rectangle([(20, 20), (240, 70)], fill="#D32F2F")
        draw.text((35, 25), "LPBS NEWS", font=logo_font, fill="white")

        # 🔥 আপডেট ৭: টেক্সট র‍্যাপিং (Text Wrapping) - যাতে লেখা কেটে না যায়
        # এবং মুখের উপর না পড়ে (নিচে সেট করা হয়েছে)
        margin = 40
        para = textwrap.wrap(title, width=45) # প্রতি লাইনে ৪৫ ক্যারেক্টার
        
        current_h = 470
        for line in para[:2]: # সর্বোচ্চ ২ লাইন প্রিন্ট করবে
            draw.text((margin, current_h), line, font=title_font, fill=(255, 255, 0), stroke_width=3, stroke_fill="black")
            current_h += 75

        # সাবটাইটেল (কল টু অ্যাকশন)
        if lang == 'bn': subtitle = "▶ ভিডিও দেখতে ক্লিক করুন"
        elif lang == 'hi': subtitle = "▶ वीडियो देखने के लिए क्लिक करें"
        else: subtitle = "▶ Watch Full Video"
        
        draw.text((margin, 630), subtitle, font=sub_font, fill="white", stroke_width=2, stroke_fill="black")

        final_img.save(PROMO_IMAGE_FILE)
        return True
    except Exception as e:
        print(f"Thumbnail Error: {e}")
        return False

# ==========================================
# 🌐 PART 3: SERVER HANDLER
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

    def update_stats(self):
        s_file = "stats.json"
        data = {"total": 0, "today": 0, "date": ""}
        if os.path.exists(s_file):
            try:
                with open(s_file, 'r') as f:
                    data = json.load(f)
            except: pass
        
        today = datetime.now().strftime("%Y-%m-%d")
        if data["date"] != today: data["date"] = today; data["today"] = 0
        data["total"] += 1; data["today"] += 1
        with open(s_file, 'w') as f: json.dump(data, f)

if __name__ == "__main__":
    # রোবট থ্রেড স্টার্ট
    robot_thread = threading.Thread(target=robot_loop)
    robot_thread.daemon = True
    robot_thread.start()
    
    print(f"🔥 LPBS SUPER-ROBOT STARTED ON PORT {PORT}")
    print(f"   👉 Retention: {RETENTION_HOURS} Hours | Deep Search: ON | Google Trends: ON")
    
    with socketserver.TCPServer(("0.0.0.0", PORT), MyRequestHandler) as httpd:
        httpd.serve_forever()
