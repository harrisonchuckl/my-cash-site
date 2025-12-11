import os
import json
import datetime
import time
import random
import textwrap
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
                title = filename.replace(".md", "").replace("-", " ").title()
                existing_titles.add(title)
    return existing_titles

def generate_topic_list(seed_category, count=10):
    print(f" 🧠  Brainstorming {count} UK topics for '{seed_category}'...")
    existing_titles = get_existing_titles()
    
    blacklist_prompt = ""
    if existing_titles:
        blacklist_sample = ", ".join(list(existing_titles)[:5]) 
        blacklist_prompt = f"DO NOT generate any titles similar to these: {blacklist_sample}. "
    
    prompt = f"Generate {count} specific 'Best X' product titles for UK market {CURRENT_YEAR}. {blacklist_prompt}Focus on items popular in Britain. Output list only."
    
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    raw_list = response.choices[0].message.content.strip().split("\n")
    
    new_topics = []
    for t in raw_list:
        clean_t = t.strip("- ").split(". ")[-1]
        if clean_t.split()[0].title() not in existing_titles:
            new_topics.append(clean_t)
        
    return new_topics[:count]

def find_real_products(topic):
    print(f"    🧠 Generating 10 UK products for: {topic}...")
    try:
        prompt = f"""
        Act as a professional UK reviewer. Your task is to generate exactly 10 distinct and specific PHYSICAL product names for '{topic}' that are currently popular and highly rated in the UK market in {CURRENT_YEAR}.
        For each product, you MUST also provide a 2-sentence summary/mini-review.
        CRITICAL INSTRUCTION: If you cannot recall 10 distinct, real product names, you MUST generate plausible, specific, and realistic-sounding model names.
        Output ONLY a valid JSON array of objects with 'name' and 'summary' fields.
        """
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        raw_output = response.choices[0].message.content.strip()

        if raw_output.startswith("```json"):
            raw_output = raw_output.replace("```json", "").replace("```", "").strip()

        if "FAIL" in raw_output.upper() or not raw_output.startswith("["):
            print("   ⚠️ AI failed to confidently generate 10 products.")
            return []
            
        product_data = json.loads(raw_output)

        products = []
        for item in product_data[:10]:
            name = item.get("name", "").strip()
            summary = item.get("summary", "").strip()
            
            if name and summary:
                # FIXED: Clean URL generation for the new "View Deal" button
                link = f"[https://www.amazon.co.uk/s?k=](https://www.amazon.co.uk/s?k=){name.replace(' ', '+')}&tag={AMAZON_TAG}"
                
                products.append({
                    "name": name, 
                    "link": link, 
                    "price_range": "Check Price £",
                    "summary": summary
                })

        return products if len(products) == 10 else []
    except Exception as e:
        print(f"   ❌ Product Generation Error: {e}")
        return []

# ==========================================
#  ✍️  MODULE 3: WRITER (POWER LIST + ADS)
# ==========================================
def create_page(topic, page_type="reviews"):
    products = find_real_products(topic) if page_type == "reviews" else []
    if not products: return False
    
    if not check_quota(): return False
    
    # Build YAML with Summaries for the new Card Layout
    products_yaml = ""
    for p in products:
        products_yaml += f'\n  - name: "{p["name"]}"\n    link: "{p["link"]}"\n    price_range: "{p["price_range"]}"\n    summary: "{p["summary"].replace("\"", "'")}"'

    # Engagement Widgets (Safeguarded with textwrap)
    engagement_html = textwrap.dedent("""
    <div id="engagement-section" style="margin-top:50px; padding:20px; background:#f8fafc; border-radius:12px; border:1px solid #eee;">
       <h3 style="text-align:center; color:#333;">Rate this Guide</h3>
       <div class="stars" onclick="rate(this)" style="text-align:center; cursor:pointer; font-size:2.5rem; color:#ff5500;">
            &#9734;&#9734;&#9734;&#9734;&#9734;
       </div>
       <p id="msg" style="display:none; text-align:center; color:green; font-weight:bold;">Thanks for voting!</p>
       <script>
            function rate(el) {
                el.innerHTML = "&#9733;&#9733;&#9733;&#9733;&#9733;";
                document.getElementById('msg').style.display='block';
                localStorage.setItem('voted_'+window.location.pathname, 'true');
            }
       </script>
       <hr style="margin: 30px 0; border-color: #eee;">
       <h3>User Reviews</h3>
       <div id="comments-placeholder">
            <p><em>Comments are enabled.</em></p>
       </div>
    </div>
    """).strip()

    prompt = f"""
    Write a Professional British English Review for '{topic}'.
    - Front Matter: title: "{topic} (UK Guide {CURRENT_YEAR})", date: today, tags: ["Reviews", "Home"]
    - Content:
      1. Professional Intro (1 Paragraph).
      2. **CRITICAL:** IMMEDIATELY after the intro, write the shortcode: {{{{< ad_mid >}}}}
      3. **CRITICAL:** Do NOT write mini-reviews/tables. I will insert the ranked cards automatically.
      4. Detailed Buying Guide.
      5. Conclusion.
    - Tone: Professional, Helpful, British spelling.
    """
    
    try:
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        body = response.choices[0].message.content.strip()
        if "---" in body: body = body.split("---", 2)[2].strip()

        # Construct Final File with NEW Ranked Cards Layout
        final_content = f"""---
title: "{topic} (UK Guide {CURRENT_YEAR})"
date: {datetime.date.today()}
description: "Professional review of the best {topic} in the UK market."
tags: ["Reviews", "Home"]
products: {products_yaml}
---

{{{{< ad_top >}}}}

<br>

{body}

<br>

{{{{< ranked_cards >}}}} <br>

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
#  🚀  MAIN CONTROL PANEL
# ==========================================
def run_god_engine():
    global OVERRIDE_ACTIVE 
    print(f"\n--- 🤖 GOD ENGINE v13.0 (Mirafit Power List) ---")
    print("1. Manual Mode\n2. Auto Mode\n3. Override")
    mode = input("Select Mode: ")
    
    if mode == "3":
        if input("Type 'YES' to override: ").upper() == 'YES': OVERRIDE_ACTIVE = True; mode = input("Select 1 or 2: ")
        else: return run_god_engine() 

    if mode == "1": create_page(input("Topic: "), "reviews")
    elif mode == "2":
        seed = input("Category: ")
        qty = int(input("Qty: "))
        for t in generate_topic_list(seed, qty):
            if not create_page(t, "reviews"): break
            time.sleep(3)

if __name__ == "__main__":
    run_god_engine()