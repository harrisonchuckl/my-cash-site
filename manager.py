import os
import json
import datetime
import time
import random
import textwrap
import re
from openai import OpenAI
from duckduckgo_search import DDGS

# ==========================================
# ⚙️  CONFIGURATION
# ==========================================
SITE_CONTENT_PATH = "./content"
SITE_START_DATE = datetime.date(2025, 12, 10) 
AMAZON_TAG = "thereviewandr-20"         
CURRENT_YEAR = datetime.date.today().year

#  🔑  READ API KEY
try:
    with open("key.txt", "r") as f:
        API_KEY = f.read().strip()
    client = OpenAI(api_key=API_KEY)
except FileNotFoundError:
    print(" ❌  ERROR: 'key.txt' not found.")
    exit()

# ==========================================
#  🛡️  MODULE 1: SAFETY MANAGER
# ==========================================
OVERRIDE_ACTIVE = False 

def check_quota():
    if OVERRIDE_ACTIVE: return True
    today = datetime.date.today()
    days_alive = (today - SITE_START_DATE).days
    if days_alive < 30: limit = 5
    elif days_alive < 60: limit = 10
    else: limit = 50
    
    log_file = "post_history.json"
    if not os.path.exists(log_file): history = {}
    else:
        with open(log_file, "r") as f: history = json.load(f)
    
    today_str = str(today)
    today_count = history.get(today_str, 0)
    print(f" 📊  Daily Quota: {today_count}/{limit}")
    
    if today_count >= limit: return False
    return True

def log_success():
    log_file = "post_history.json"
    today_str = str(datetime.date.today())
    if os.path.exists(log_file):
        with open(log_file, "r") as f: history = json.load(f)
    else: history = {}
    history[today_str] = history.get(today_str, 0) + 1
    with open(log_file, "w") as f: json.dump(history, f)

# ==========================================
#  🧠  MODULE 2: BRAIN & RESEARCHER
# ==========================================
def get_existing_titles():
    existing_titles = set()
    reviews_path = os.path.join(SITE_CONTENT_PATH, "reviews")
    if os.path.exists(reviews_path):
        for filename in os.listdir(reviews_path):
            if filename.endswith(".md"):
                title = filename.replace(".md", "").replace("-", " ").title()
                existing_titles.add(title)
    return existing_titles

def generate_topic_list(seed_category, count=10):
    print(f" 🧠  Brainstorming {count} UK topics for '{seed_category}'...")
    existing_titles = get_existing_titles()
    blacklist_prompt = f"DO NOT generate titles similar to: {', '.join(list(existing_titles)[:5])}." if existing_titles else ""
    
    # FIX: Instruct AI to NOT include the year in the list
    prompt = f"Generate {count} specific 'Best X' product titles for UK market. Do NOT include the year '{CURRENT_YEAR}' in the strings. Focus on items popular in Britain. Output list only."
    
    try:
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        raw_list = response.choices[0].message.content.strip().split("\n")
        return [t.strip("- ").split(". ")[-1] for t in raw_list if t.strip("- ").split(". ")[-1] not in existing_titles][:count]
    except: return []

def find_real_products(topic):
    print(f"    🧠 Researching products for: {topic}...")
    try:
        # We search WITH the year to get new items, but we don't put it in the title later
        with DDGS() as ddgs:
            results = list(ddgs.text(f"best rated {topic} amazon uk {CURRENT_YEAR} reviews", max_results=8))
        
        prompt = f"""
        Act as an Expert Product Researcher for the UK market.
        Based on search results: {str(results)}.
        Identify the 10 BEST products for '{topic}'.
        
        CRITERIA:
        1. Real products available in the UK.
        2. Assign a realistic "Expert Score" (e.g. 9.8, 9.5).
        3. Estimate reviews (e.g., "1,500+").
        
        Output ONLY a valid JSON array:
        [ {{ "name": "Product Name", "summary": "Why it's good.", "score": "9.8", "reviews": "1,500+" }} ]
        """
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        raw_output = response.choices[0].message.content.strip()
        
        if "```" in raw_output:
            raw_output = raw_output.split("```json")[-1].split("```")[0].strip() if "json" in raw_output else raw_output.split("```")[-1].strip()
            
        product_data = json.loads(raw_output)
        products = []
        
        for item in product_data[:10]:
            name = item.get("name", "").strip()
            summary = item.get("summary", "").strip()
            if name:
                link = f"https://www.amazon.co.uk/s?k={name.replace(' ', '+')}&tag={AMAZON_TAG}"
                products.append({
                    "name": name, "link": link, "price_range": "Check Price £", 
                    "summary": summary, "score": item.get("score", "9.0"), 
                    "review_count": item.get("reviews", "100+")
                })
        return products
    except Exception as e:
        print(f"   ⚠️ Research Error: {e}")
        return []

# ==========================================
#  ✍️  MODULE 3: WRITER
# ==========================================
def create_page(topic, page_type="reviews"):
    # --- V15.3 FIX: THE TIME MACHINE CLEANER ---
    # 1. Regex removes "2025", "in 2025", "of 2025" case insensitive
    clean_topic = re.sub(r'\b(?:in\s+|of\s+)?20\d{2}\b', '', topic, flags=re.IGNORECASE).strip()
    # 2. Remove File-Breaking Characters (: " /)
    safe_topic = clean_topic.replace(":", "").replace('"', '').replace("/", " ").strip()
    
    products = find_real_products(safe_topic) if page_type == "reviews" else []
    if not products: return False
    if not check_quota(): return False
    
    products_yaml = ""
    for p in products:
        products_yaml += f'\n  - name: "{p["name"]}"\n    link: "{p["link"]}"\n    price_range: "{p["price_range"]}"\n    summary: "{p["summary"].replace("\"", "")}"\n    score: "{p["score"]}"\n    review_count: "{p["review_count"]}"'

    engagement_html = textwrap.dedent("""
    <div id="engagement-section" style="margin-top:60px; padding:30px; background:#ffffff; border:1px solid #e5e7eb; border-radius:12px; text-align:center;">
       <h3 style="color:#111827; font-weight:800; margin-bottom:1rem;">Was this guide helpful?</h3>
       <div class="stars" onclick="rate(this)" style="cursor:pointer; font-size:2.5rem; color:#ff5500; letter-spacing:5px;">&#9734;&#9734;&#9734;&#9734;&#9734;</div>
       <p id="msg" style="display:none; color:#059669; font-weight:bold; margin-top:10px;">Thank you for your feedback.</p>
       <script>function rate(el){el.innerHTML="&#9733;&#9733;&#9733;&#9733;&#9733;";document.getElementById('msg').style.display='block';localStorage.setItem('voted_'+window.location.pathname,'true');}</script>
       <hr style="margin: 30px 0; border-color: #e5e7eb;">
       <h3 style="color:#111827; font-weight:800;">Discussion</h3>
       <div id="comments-placeholder"><p style="color:#6b7280;"><em>Community comments are currently enabled.</em></p></div>
    </div>
    """).strip()

    prompt = f"""
    Write a High-Authority British English Review for '{safe_topic}'.
    - Title: "{safe_topic}" (NO YEARS)
    - Intro: Hook reader. Ad injection: {{{{< ad_mid >}}}}.
    - Body: "## Top Picks". Buying Guide. FAQ (4 questions).
    - Tone: Expert, British. NO EMOJIS. NO YEARS in headers.
    """
    
    try:
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        body = response.choices[0].message.content.strip().replace("---", "")

        final_content = f"""---
title: "{safe_topic}"
date: {datetime.date.today()}
description: "Professional review of the best {safe_topic} in the UK market. Regularly updated rankings."
tags: ["Reviews", "Home"]
products: {products_yaml}
---

<div class="update-notice" style="background:#f0fdf4; color:#166534; padding:10px; border-radius:6px; font-size:0.9rem; margin-bottom:20px; border:1px solid #bbf7d0;">
    <strong>✅ Live Ranking:</strong> We regularly update this page to ensure you see the latest products and prices.
</div>

{{{{< ad_top >}}}}

<br>

{body}

<br>

{{{{< ranked_cards >}}}} 

<br>

{{{{< ad_footer >}}}}

{engagement_html}
"""
        filename = safe_topic.lower().replace(" ", "-")[:50] + ".md"
        with open(os.path.join(SITE_CONTENT_PATH, page_type, filename), "w") as f: f.write(final_content)
        log_success()
        print(f"    ✅  PUBLISHED: {filename}")
        return True
    except Exception as e:
        print(f"    ❌  Error: {e}")
        return False

# ==========================================
#  🔄  MODULE 4: UPDATE ENGINE
# ==========================================
def update_all_pages():
    print(" 🔄  STARTING MASS UPDATE...")
    path = os.path.join(SITE_CONTENT_PATH, "reviews")
    if not os.path.exists(path): return
    for f in os.listdir(path):
        if f.endswith(".md"):
            # Strips year from filename title too
            topic = f.replace(".md", "").replace("-", " ").title()
            clean_topic = re.sub(r'\b(?:in\s+|of\s+)?20\d{2}\b', '', topic, flags=re.IGNORECASE).strip()
            print(f" ♻️  Updating: {clean_topic}...")
            create_page(clean_topic, "reviews")
            time.sleep(2)

def run_god_engine():
    global OVERRIDE_ACTIVE 
    print(f"\n--- 🤖 GOD ENGINE v15.3 (Timeless Edition) ---")
    mode = input("1. Manual\n2. Auto\n3. Override\n4. Update All\nSelect: ")
    if mode == "3": OVERRIDE_ACTIVE = True; mode = input("Select 1, 2 or 4: ")
    
    if mode == "1": create_page(input("Topic: "), "reviews")
    elif mode == "2":
        seed = input("Category: ")
        qty = int(input("Qty: "))
        for t in generate_topic_list(seed, qty):
            if not create_page(t, "reviews"): break
            time.sleep(3)
    elif mode == "4": update_all_pages()

if __name__ == "__main__":
    run_god_engine()
    