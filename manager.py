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

def clean_year_from_text(text):
    """Aggressively removes years (2024-2026) from any string."""
    cleaned = re.sub(r'[\(\[\-]?\b(?:in\s+|of\s+)?20[2-3]\d\b[\)\]]?', '', text, flags=re.IGNORECASE)
    return cleaned.strip()

def sanitize_filename(title):
    """Forces filename to be lowercase alphanumeric only."""
    clean = clean_year_from_text(title)
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', clean)
    return clean.lower().strip().replace(" ", "-")[:60] + ".md"

# ==========================================
#  🧠  MODULE 2: BRAIN & RESEARCHER (FULL TEXT UPGRADE)
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
    
    prompt = f"Generate {count} specific 'Best X' product titles for the category '{seed_category}' for the UK market. Do NOT include the year '{CURRENT_YEAR}' in the strings. Output list only."
    
    try:
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        raw_list = response.choices[0].message.content.strip().split("\n")
        # Clean years immediately from the brainstormed list
        return [clean_year_from_text(t.strip("- ").split(". ")[-1]) for t in raw_list if t.strip("- ").split(". ")[-1] not in existing_titles][:count]
    except: return []

def find_real_products(topic):
    print(f"    🧠 Researching products for: {topic}...")
    try:
        with DDGS() as ddgs:
            # We add "products" to the search to help filter out blog posts about general ideas
            results = list(ddgs.text(f"best top rated {topic} models uk reviews", max_results=8))
        
        # --- SAFEGUARDED: STRICT FILTERING + NEW FULL PARAGRAPH REQUEST ---
        prompt = f"""
        Act as a Strict Product Data Validator for the UK market.
        Your Goal: Extract exactly 10 distinct, physical product names for '{topic}' based on: {str(results)}.

        CRITICAL FILTERING RULES:
        1. **Strict Relevance:** The product MUST be the actual item described in '{topic}', NOT an accessory. 
           - Example: If topic is "Tea Sets", return actual Teapots/Cups. REJECT "Cake Stands", "Spoons", or "Tea Towels".
           - Example: If topic is "Laptops", REJECT "Laptop Cases".
        2. **Core Definition:** If the search results contain mostly accessories (like cake stands), IGNORE THEM and instead generate real, highly-rated model names that fit the TRUE definition of '{topic}'.
        3. **UK Availability:** Must be sold in the UK.

        Output ONLY a valid JSON array:
        [ {{ "name": "Product Name", "summary": "Write a detailed 3-4 sentence mini-review (approx 50 words) explaining EXACTLY why this product is a top pick. Mention specific features.", "score": "9.8", "reviews": "1,500+" }} ]
        """
        
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        raw_output = response.choices[0].message.content.strip()
        
        if "```" in raw_output:
            raw_output = raw_output.split("```json")[-1].split("```")[0].strip() if "json" in raw_output else raw_output.split("```")[-1].strip()
            
        product_data = json.loads(raw_output)
        products = []
        
        for item in product_data[:10]:
            name = clean_year_from_text(item.get("name", "").strip())
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
#  ✍️  MODULE 3: WRITER (ROYAL BLUE DESIGN + HIGH GRID)
# ==========================================
def create_page(topic, page_type="reviews"):
    safe_topic = clean_year_from_text(topic)
    
    products = find_real_products(safe_topic) if page_type == "reviews" else []
    if not products: return False
    if not check_quota(): return False
    
    products_yaml = ""
    for p in products:
        # Sanitize summary to prevent YAML breaks with quotes
        clean_summary = p["summary"].replace("\"", "").replace("'", "")
        products_yaml += f'\n  - name: "{p["name"]}"\n    link: "{p["link"]}"\n    price_range: "{p["price_range"]}"\n    summary: "{clean_summary}"\n    score: "{p["score"]}"\n    review_count: "{p["review_count"]}"'

    # UPDATED: Royal Blue/Gold Engagement Section with GISCUS
    engagement_html = textwrap.dedent("""
    <div id="engagement-section" style="margin-top:60px; padding:30px; background:#ffffff; border:1px solid #e5e7eb; border-radius:12px; text-align:center;">
       <h3 style="color:#1e3a8a; font-weight:800; margin-bottom:1rem;">Was this guide helpful?</h3>
       <div class="stars" onclick="rate(this)" style="cursor:pointer; font-size:2.5rem; color:#d97706; letter-spacing:5px; transition: transform 0.2s;">&#9734;&#9734;&#9734;&#9734;&#9734;</div>
       <p id="msg" style="display:none; color:#059669; font-weight:bold; margin-top:10px;">Thank you for your feedback!</p>
       <script>function rate(el){el.innerHTML="&#9733;&#9733;&#9733;&#9733;&#9733;";document.getElementById('msg').style.display='block';localStorage.setItem('voted_'+window.location.pathname,'true');}</script>
       
       <hr style="margin: 40px 0; border-color: #e5e7eb;">
       
       <h3 style="color:#1e3a8a; font-weight:800; margin-bottom: 20px;">Join the Discussion</h3>
       <script src="https://giscus.app/client.js"
        data-repo="harrisonchuckl/my-cash-site"
        data-repo-id="R_kgDONN3QQA" 
        data-category="General"
        data-category-id="DIC_kwDONN3QQM4CkM3k"
        data-mapping="pathname"
        data-strict="0"
        data-reactions-enabled="1"
        data-emit-metadata="0"
        data-input-position="bottom"
        data-theme="light"
        data-lang="en"
        crossorigin="anonymous"
        async>
        </script>
        </div>
    """).strip()

    # UPDATED: Prompt asks AI to stop after Intro (so we can insert Grid)
    prompt = f"""
    Write a High-Authority British English Review for '{safe_topic}'.
    - Title: "{safe_topic}"
    - Intro: Hook reader (max 150 words). Ad injection: {{{{< ad_mid >}}}}.
    - Body Structure: 
      1. Intro
      2. **STOP WRITING HERE.** (I will insert the Product List automatically)
      3. Buying Guide (Detailed)
      4. FAQ (4 questions)
    - Tone: Expert, British. NO EMOJIS.
    """
    
    try:
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        body = response.choices[0].message.content.strip().replace("---", "")
        body = clean_year_from_text(body) 

        # --- UPDATED: REORDERED CONTENT STRUCTURE (Grid Moved Up) ---
        # 1. Intro/Ad
        # 2. **RANKED CARDS (Top 10)**
        # 3. Buying Guide
        final_content = f"""---
title: "{safe_topic}"
date: {datetime.date.today()}
description: "Professional review of the best {safe_topic} in the UK market. Regularly updated rankings."
tags: ["Reviews", "Home"]
products: {products_yaml}
---

<div class="update-notice" style="background:#f0f9ff; color:#0369a1; padding:12px; border-radius:8px; font-size:0.95rem; margin-bottom:25px; border:1px solid #bae6fd; display:flex; align-items:center; gap:10px;">
    <span>✅ <strong>Live Ranking:</strong> Regularly updated for {CURRENT_YEAR}.</span>
</div>

{{{{< ad_top >}}}}

<br>

{body.split("Buying Guide")[0] if "Buying Guide" in body else body[:500]} 

<br>

{{{{< ranked_cards >}}}} 

<br>

## Buying Guide
{body.split("Buying Guide")[1] if "Buying Guide" in body else ""}

<br>

{{{{< ad_footer >}}}}

{engagement_html}
"""
        filename = sanitize_filename(safe_topic)
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
            topic = f.replace(".md", "").replace("-", " ").title()
            clean_topic = clean_year_from_text(topic)
            print(f" ♻️  Updating: {clean_topic}...")
            create_page(clean_topic, "reviews")
            time.sleep(2)

def run_god_engine():
    global OVERRIDE_ACTIVE 
    print(f"\n--- 🤖 GOD ENGINE v19.0 (Full Text + Green Buttons) ---")
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