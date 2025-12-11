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
    
    print(f" 📊  Daily Quota: {today_count}/{limit} | Site Age: {days_alive} days")
    
    if today_count >= limit:
        print(f" 🛑  DAILY LIMIT REACHED. Stopping.")
        return False
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
                # Convert "best-kettles.md" -> "Best Kettles"
                title = filename.replace(".md", "").replace("-", " ").title()
                existing_titles.add(title)
    return existing_titles

def generate_topic_list(seed_category, count=10):
    print(f" 🧠  Brainstorming {count} UK topics for '{seed_category}'...")
    existing_titles = get_existing_titles()
    blacklist_prompt = f"DO NOT generate titles similar to: {', '.join(list(existing_titles)[:5])}." if existing_titles else ""
    
    prompt = f"Generate {count} specific 'Best X' product titles for UK market {CURRENT_YEAR}. {blacklist_prompt}Focus on items popular in Britain. Output list only."
    
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    raw_list = response.choices[0].message.content.strip().split("\n")
    
    # Simple deduplication
    clean_list = []
    for t in raw_list:
        clean = t.strip("- ").split(". ")[-1]
        if clean not in existing_titles:
            clean_list.append(clean)
            
    return clean_list[:count]

def find_real_products(topic):
    print(f"    🧠 Researching Top 10 High-Rated UK products for: {topic}...")
    try:
        # Search specifically for "Best [Topic] UK Reviews" to get high-quality items
        with DDGS() as ddgs:
            results = list(ddgs.text(f"best rated {topic} amazon uk {CURRENT_YEAR} reviews", max_results=10))
        
        context = str(results)

        prompt = f"""
        Act as an Expert Product Researcher for the UK market.
        Based on these search results: {context} AND your internal knowledge of high-performing brands in the UK.
        
        Identify the 10 BEST products for '{topic}'.
        
        CRITERIA:
        1. Must be real products available in the UK.
        2. Prioritize products with HIGH review counts (1000+).
        3. Assign a realistic "Expert Score" (out of 10) based on quality (e.g. 9.8, 9.5, 9.1). NOT just 10, 9, 8.
        4. Estimate the review count (e.g., "2,500+", "1,200+").
        
        Output ONLY a valid JSON array of objects:
        [
            {{
                "name": "Exact Product Name", 
                "summary": "2-sentence why it's good.",
                "score": "9.8",
                "reviews": "1,500+"
            }}
        ]
        """
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        raw_output = response.choices[0].message.content.strip()
        
        # Clean JSON markdown if present
        if "```json" in raw_output:
            raw_output = raw_output.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_output:
            raw_output = raw_output.split("```")[0].strip()
            
        product_data = json.loads(raw_output)
        products = []
        
        for item in product_data[:10]:
            name = item.get("name", "").strip()
            summary = item.get("summary", "").strip()
            score = item.get("score", "9.0")
            reviews = item.get("reviews", "100+")
            
            if name and summary:
                link = f"[https://www.amazon.co.uk/s?k=](https://www.amazon.co.uk/s?k=){name.replace(' ', '+')}&tag={AMAZON_TAG}"
                products.append({
                    "name": name, 
                    "link": link, 
                    "price_range": "Check Price £", 
                    "summary": summary,
                    "score": score,
                    "review_count": reviews
                })

        return products if len(products) == 10 else []
    except Exception as e:
        print(f"   ❌ Product Research Error: {e}")
        return []

# ==========================================
#  ✍️  MODULE 3: WRITER (AUTHORITY CONTENT)
# ==========================================
def create_page(topic, page_type="reviews"):
    products = find_real_products(topic) if page_type == "reviews" else []
    if not products: return False
    
    # If using Override/Update mode, we skip quota check usually, but let's keep it safe
    if not check_quota(): return False
    
    # Build YAML with NEW Fields (Score, Reviews)
    products_yaml = ""
    for p in products:
        products_yaml += f'\n  - name: "{p["name"]}"\n    link: "{p["link"]}"\n    price_range: "{p["price_range"]}"\n    summary: "{p["summary"].replace("\"", "'")}"\n    score: "{p["score"]}"\n    review_count: "{p["review_count"]}"'

    # Engagement Widgets
    engagement_html = textwrap.dedent("""
    <div id="engagement-section" style="margin-top:60px; padding:30px; background:#ffffff; border:1px solid #e5e7eb; border-radius:12px; text-align:center;">
       <h3 style="color:#111827; font-weight:800; margin-bottom:1rem;">Was this guide helpful?</h3>
       <div class="stars" onclick="rate(this)" style="cursor:pointer; font-size:2.5rem; color:#ff5500; letter-spacing:5px;">
            &#9734;&#9734;&#9734;&#9734;&#9734;
       </div>
       <p id="msg" style="display:none; color:#059669; font-weight:bold; margin-top:10px;">Thank you for your feedback.</p>
       <script>
            function rate(el) {
                el.innerHTML = "&#9733;&#9733;&#9733;&#9733;&#9733;";
                document.getElementById('msg').style.display='block';
                localStorage.setItem('voted_'+window.location.pathname, 'true');
            }
       </script>
       <hr style="margin: 30px 0; border-color: #e5e7eb;">
       <h3 style="color:#111827; font-weight:800;">Discussion</h3>
       <div id="comments-placeholder">
            <p style="color:#6b7280;"><em>Community comments are currently enabled.</em></p>
       </div>
    </div>
    """).strip()

    # V15 PROMPT: No Fluff, FAQ, Updates
    prompt = f"""
    Write a High-Authority British English Review for '{topic}'.
    
    - **Front Matter:** - Title: "{topic} (UK Guide {CURRENT_YEAR})"
      - Date: {datetime.date.today()}
      - Tags: ["Reviews", "Home"]
    
    - **Content Guidelines:**
      1. **Intro (Journalist Style):** NO generic "In today's world" fluff. Start with the problem and the solution immediately. Mention that this list is updated for {CURRENT_YEAR}.
      2. **Ad Injection:** Write {{{{< ad_mid >}}}} immediately after the intro.
      3. **The List:** Do NOT write the product list text. Just write: "## Top 10 Picks for {CURRENT_YEAR}" and then I will insert the widget.
      4. **Buying Guide:** deeply detailed, technical but accessible.
      5. **FAQ Section:** Write a "Frequently Asked Questions" section with 4-5 common questions about {topic} and helpful answers.
      6. **"See Also":** A small section recommending checking other reviews in the Home category.
      
    - **Tone:** Authoritative, Expert, British (Colour, Optimised). NO EMOJIS.
    """
    
    try:
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        body = response.choices[0].message.content.strip()
        if "---" in body: body = body.split("---", 2)[2].strip()

        final_content = f"""---
title: "{topic} (UK Guide {CURRENT_YEAR})"
date: {datetime.date.today()}
description: "Professional review of the best {topic} in the UK market. Updated for {CURRENT_YEAR}."
tags: ["Reviews", "Home"]
products: {products_yaml}
---

<div class="update-notice" style="background:#f0fdf4; color:#166534; padding:10px; border-radius:6px; font-size:0.9rem; margin-bottom:20px; border:1px solid #bbf7d0;">
    <strong>✅ Updated for {CURRENT_YEAR}:</strong> We regularly update this page to ensure you see the latest products and prices.
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
        
        filename = topic.lower().replace(" ", "-")[:50] + ".md"
        path = os.path.join(SITE_CONTENT_PATH, page_type, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f: f.write(final_content)
            
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
    print(" 🔄  STARTING MASS UPDATE (Refreshing Content)...")
    reviews_path = os.path.join(SITE_CONTENT_PATH, "reviews")
    if not os.path.exists(reviews_path):
        print("No reviews found to update.")
        return

    files = [f for f in os.listdir(reviews_path) if f.endswith(".md")]
    print(f"Found {len(files)} pages to update.")
    
    for filename in files:
        # Extract topic from filename (best-kettles.md -> Best Kettles)
        topic = filename.replace(".md", "").replace("-", " ").title()
        print(f" ♻️  Updating: {topic}...")
        create_page(topic, "reviews") # This overwrites the old file with new data
        time.sleep(2) # Safety pause

# ==========================================
#  🚀  MAIN CONTROL PANEL
# ==========================================
def run_god_engine():
    global OVERRIDE_ACTIVE 
    print(f"\n--- 🤖 GOD ENGINE v15.0 (Authority & SEO) ---")
    print("1. Manual Mode (Write 1 page)")
    print("2. Auto-Discovery (New pages)")
    print("3. Override Safety Limits")
    print("4. ♻️ UPDATE ALL EXISTING PAGES (Fresh Data)")
    
    mode = input("Select Mode: ")
    
    if mode == "3":
        if input("Type 'YES' to override: ").upper() == 'YES': OVERRIDE_ACTIVE = True; mode = input("Select 1, 2 or 4: ")
        else: return run_god_engine() 

    if mode == "1": create_page(input("Topic: "), "reviews")
    elif mode == "2":
        seed = input("Category: ")
        qty = int(input("Qty: "))
        for t in generate_topic_list(seed, qty):
            if not create_page(t, "reviews"): break
            time.sleep(3)
    elif mode == "4":
        update_all_pages()

if __name__ == "__main__":
    run_god_engine()
