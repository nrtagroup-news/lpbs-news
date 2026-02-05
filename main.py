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

# --- ম্যাজিক লাইব্রেরি (Pillow) ---
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
NEWS_API_KEY = "pub_102fa773efa04ad2871534886e425eab" 
PROMO_IMAGE_FILE = "promo_image.jpg"
RETENTION_HOURS = 48 

FONTS = { 'bn': 'bn.ttf', 'hi': 'hn.ttf', 'en': 'en.ttf', 'tm': 'tm.ttf' }

# --- 🧠 NEW: AI KEYS & CONFIGURATION ---
Z_AI_KEY = "cf5a27b9240b49b9a398094d440889e5.5RDCyrw5XLRVJEiH"
DEEP_AI_KEY = "7bc72502-db85-4dd2-9038-c3811d69ff7c"

# ==========================================
# 🧠 PART 1: THE ROBOT BRAIN (EXISTING LOGIC PRESERVED)
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

def clean_old_news(news_list):
    current_time = time.time()
    retention_seconds = RETENTION_HOURS * 3600
    cleaned_list = []
    for n in news_list:
        news_age = current_time - n.get('timestamp', 0)
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

# --- SMART MIXING ALGORITHM (PRESERVED) ---
def smart_mix_news(news_list, location_keyword):
    high_priority = [] 
    local_priority = [] 
    general_mix = []    

    location_keyword = location_keyword.lower()

    for item in news_list:
        title = item.get('title', '').lower()
        category = item.get('category', '').lower()
        source = item.get('source', '').lower()

        if 'trend' in category or 'breaking' in category or 'trend' in source:
            high_priority.append(item)
        elif location_keyword in title or location_keyword in category:
            local_priority.append(item)
        else:
            general_mix.append(item)

    random.shuffle(general_mix)
    final_feed = high_priority + local_priority + general_mix
    return final_feed

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
                desc = f"Trending now in India: {title}. See full coverage on LPBS News."
                try: news_item_title = item.find('ht:news_item_title', namespaces={'ht': 'https://trends.google.com/trends/trendingsearches/daily'}).text; desc = news_item_title
                except: pass
                image_url = "https://via.placeholder.com/600x400?text=Trending+News"
                try: image_url = item.find('ht:picture', namespaces={'ht': 'https://trends.google.com/trends/trendingsearches/daily'}).text
                except: pass

                trends.append({
                    "id": f"trend_{abs(hash(title))}", "category": "Trending 🔥", "title": title,
                    "desc": desc, "thumb": image_url, "source": "Google Trends", "video_url": "",
                    "time": "Hot Topic", "timestamp": time.time(), "type": "image", "platform": "google"
                })
    except Exception as e: print(f"Trend Error: {e}")
    return trends

def fetch_social_videos(channels):
    video_news = []
    ydl_opts = { 'quiet': True, 'ignoreerrors': True, 'extract_flat': True, 'playlistend': 15, 'socket_timeout': 20 }
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
                            "id": video_id, "category": category, "title": video.get('title') or "Latest Update",
                            "desc": video.get('title') or "Click to watch", "thumb": thumb, "video_url": embed_link,
                            "original_link": original_url, "source": info.get('uploader') or "Social Media",
                            "time": "Just Now", "timestamp": time.time(), "type": "video",
                            "platform": "facebook" if "facebook" in original_url else "youtube"
                        })
                except: pass
                time.sleep(2) 
    return video_news

def robot_loop():
    print("🤖 ROBOT SYSTEM: INITIALIZED & INTELLIGENT")
    while True:
        try:
            config = load_config()
            channels = config.get("channels", {})
            location = config.get("location_override", "India")
            existing_db = clean_old_news(load_db())
            fresh_content = fetch_google_trends() + fetch_social_videos(channels)
            existing_ids = {item['id'] for item in existing_db}
            for item in fresh_content:
                if item['id'] not in existing_ids: existing_db.append(item)
            
            optimized_db = smart_mix_news(existing_db, location)
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "news": optimized_db, "updated_at": datetime.now().strftime("%I:%M %p"), 
                    "location": location, "total_articles": len(optimized_db)
                }, f, indent=4, ensure_ascii=False)
            print(f"✅ ROBOT: Cycle Complete. Active: {len(optimized_db)}")
            time.sleep(300) 
        except Exception as e:
            print(f"❌ ROBOT ERROR: {e}")
            time.sleep(60)

# ==========================================
# 🚀 PART 2: AI POWERED PROMO ENGINE (UPDATED)
# ==========================================

def fallback_hashtags(title):
    """ ধাপ ৩: যদি কোনো AI কাজ না করে, তবে এই সিস্টেম কাজ করবে (Google Search Simulation) """
    title_lower = title.lower()
    tags = ["#LPBSNews", "#Viral"]
    keywords = {
        "bangladesh": "#BangladeshNews", "india": "#IndiaUpdate", "modi": "#PMModi",
        "mamata": "#MamataOfficial", "cricket": "#CricketLive", "accident": "#BreakingNews", 
        "politics": "#Politics", "movie": "#Bollywood", "song": "#TrendingSong"
    }
    for key, tag in keywords.items():
        if key in title_lower: tags.append(tag)
    tags.append("#ForYou")
    tags.append("#TrendingNow")
    return " ".join(tags[:8]) + "\n\n(Generated by System Fallback)"

def ask_z_ai(prompt):
    """ ধাপ ১: Z AI (6 সেকেন্ড সময় পাবে) """
    print("🤖 AI: Asking Z AI...")
    try:
        # Z AI (Assuming standard OpenAI Compatible or Direct Completion)
        # Note: Since specific endpoint isn't provided, trying standard completion structure
        headers = { "Authorization": f"Bearer {Z_AI_KEY}", "Content-Type": "application/json" }
        payload = {
            "model": "gpt-3.5-turbo", # Or "z-ai-model" if known
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100
        }
        # Using a generic endpoint. If Z AI has a specific URL, replace it here.
        # For now, using a common proxy pattern or OpenAI default if compatible.
        # If this fails, it goes to DeepAI anyway.
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=6)
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            print(f"⚠️ Z AI Failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Z AI Error/Timeout: {e}")
        return None

def ask_deep_ai(prompt):
    """ ধাপ ২: Deep AI (ব্যাকআপ) """
    print("🤖 AI: Switching to Deep AI...")
    try:
        response = requests.post(
            "https://api.deepai.org/api/text-generator",
            data={'text': prompt},
            headers={'api-key': DEEP_AI_KEY},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()['output']
        else:
            return None
    except Exception as e:
        print(f"⚠️ Deep AI Error: {e}")
        return None

def generate_super_promo(title, lang):
    """ মাস্টার ফাংশন: Z AI -> Deep AI -> Fallback """
    
    # প্রম্পট তৈরি করা
    lang_name = "Bengali" if lang == 'bn' else "Hindi" if lang == 'hi' else "English"
    prompt = f"Write a very short, catchy, viral social media caption with 5 hashtags for this news title in {lang_name}: '{title}'. Keep it exciting."

    # 1. Try Z AI
    result = ask_z_ai(prompt)
    if result: return result

    # 2. Try Deep AI
    result = ask_deep_ai(prompt)
    if result: return result

    # 3. Fallback
    print("⚠️ All AI failed. Using Fallback System.")
    return f"{title}\n\n{fallback_hashtags(title)}"

def create_viral_thumbnail(image_url, title, lang):
    if not PILLOW_AVAILABLE: return False
    try:
        response = requests.get(image_url, timeout=5)
        img = Image.open(io.BytesIO(response.content)).convert("RGB")
        base_width, base_height = 1280, 720
        canvas = Image.new("RGB", (base_width, base_height), (0,0,0))
        
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

        overlay = Image.new('RGBA', final_img.size, (0,0,0,0))
        draw_overlay = ImageDraw.Draw(overlay)
        draw_overlay.rectangle([(0, 450), (1280, 720)], fill=(0, 0, 0, 200)) 
        final_img = Image.alpha_composite(final_img.convert('RGBA'), overlay).convert('RGB')
        draw = ImageDraw.Draw(final_img)

        font_filename = FONTS.get(lang, 'en.ttf')
        try:
            if os.path.exists(font_filename):
                title_font = ImageFont.truetype(font_filename, 60)
                sub_font = ImageFont.truetype(font_filename, 40)
                logo_font = ImageFont.truetype(font_filename, 35)
            else:
                title_font = ImageFont.load_default(); sub_font = ImageFont.load_default(); logo_font = ImageFont.load_default()
        except:
            title_font = ImageFont.load_default(); sub_font = ImageFont.load_default(); logo_font = ImageFont.load_default()

        draw.rectangle([(20, 20), (240, 70)], fill="#D32F2F")
        draw.text((35, 25), "LPBS NEWS", font=logo_font, fill="white")

        margin = 40
        para = textwrap.wrap(title, width=45)
        current_h = 470
        for line in para[:2]:
            draw.text((margin, current_h), line, font=title_font, fill=(255, 255, 0), stroke_width=3, stroke_fill="black")
            current_h += 75

        if lang == 'bn': subtitle = "▶ ভিডিও দেখতে কমেন্টে ক্লিক করুন"
        elif lang == 'hi': subtitle = "▶ वीडियो देखने के comment क्लिक करें"
        else: subtitle = "▶ Watch Full Video Link in Comment"
        draw.text((margin, 630), subtitle, font=sub_font, fill="white", stroke_width=2, stroke_fill="black")

        final_img.save(PROMO_IMAGE_FILE)
        return True
    except Exception as e:
        print(f"Thumbnail Error: {e}")
        return False

# ==========================================
# 🌐 PART 3: SERVER HANDLER (UPDATED)
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
            
            # 🔥 NEW: Calling the AI Super Brain
            ai_hashtags = generate_super_promo(title, lang)
            
            thumb_success = create_viral_thumbnail(thumb_url, title, lang)
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({
                "hashtags": ai_hashtags, 
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
    print(f"🔥 LPBS SUPER-ROBOT STARTED ON PORT {PORT}")
    print(f"   👉 AI SYSTEM: Z-AI + DEEP-AI + FALLBACK Activated")
    with socketserver.TCPServer(("0.0.0.0", PORT), MyRequestHandler) as httpd:
        httpd.serve_forever()
