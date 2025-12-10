import os
import json
import datetime
import time
import random
from openai import OpenAI
from duckduckgo_search import DDGS

# ==========================================
# ⚙️  CONFIGURATION
# ==========================================
SITE_CONTENT_PATH = "./content"
SITE_START_DATE = datetime.date(2025, 12, 10) 
AMAZON_TAG = "yourtag-21"         
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
def check_quota():
    today = datetime.date.today()
    days_alive = (today - SITE_START_DATE).days
    
    # Safe Speed Limits
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
def generate_topic_list(seed_category, count=10):
    print(f" 🧠  Brainstorming {count} UK topics for '{seed_category}'...")
    prompt = f"Generate {count} specific 'Best X' product titles for UK market {CURRENT_YEAR}. Focus on items popular in Britain. Output list only."
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    raw = response.choices[0].message.content.strip().split("\n")
    return [t.strip("- ").split(". ")[-1] for t in raw if t]

def find_real_products(topic):
    print(f"    🔎  Researching 10 UK products for: {topic}...")
    try:
        with DDGS() as ddgs:
            # Search deeper to find 10 unique product names
            results = list(ddgs.text(f"best top rated {topic} uk {CURRENT_YEAR} reviews", max_results=30))
        if not results: return []
        
        # We ask for 10 distinct names
        prompt = f"From the following UK snippets, extract 10 distinct and specific PHYSICAL product names (e.g., 'Ninja AF101', 'Simplehuman Sensor Mirror'). Return ONLY a comma-separated list of names. Snippets: {str(results)}"
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        names = response.choices[0].message.content.split(",")
        
        # --- CRITICAL NEW GUARDRAIL ---
        products = []
        cleaned_names = [n.strip() for n in names if n.strip()][:10]
        
        if len(cleaned_names) < 5:
            print(f"   ⚠️ AI only found {len(cleaned_names)} specific products. Skipping topic to prevent crash.")
            return []
        # --------------------------------

        for name in cleaned_names:
            # UK Affiliate Search Link
            link = f"https://www.amazon.co.uk/s?k={name.replace(' ', '+')}&tag={AMAZON_TAG}"
            # Add dynamic placeholder for the grid
            products.append({
                "name": name, 
                "link": link, 
                "price_range": "Check Price £" 
            })
        return products
    except Exception as e:
        print(f"   ❌ Final Search Error: {e}")
        return []

# ==========================================
#  ✍️  MODULE 3: WRITER (PROFESSIONAL GRID)
# ==========================================
def create_page(topic, page_type="reviews"):
    # Exit if Quota is hit OR if product finder returned < 5 products
    products = find_real_products(topic) if page_type == "reviews" else []
    if not products: return False
    if not check_quota(): return False
    
    # 1. Build Product YAML for Front Matter (Required for the new Grid Layout)
    products_yaml = ""
    for p in products:
        products_yaml += f"\n  - name: \"{p['name']}\"\n    link: \"{p['link']}\"\n    price_range: \"{p['price_range']}\""

    # 2. Engagement Widgets (Combined: Stars + Comments)
    engagement_html = """
    <div id="engagement-section" style="margin-top:50px; padding:20px; background:#f8fafc; border-radius:12px;">
       <h3 style="text-align:center;">Rate this Guide</h3>
       <div class="stars" onclick="rate(this)" style="text-align:center; cursor:pointer; font-size:2.5rem; color:#f59e0b;">
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

       <hr style="margin: 30px 0; border-color: #e2e8f0;">
       <h3>User Reviews</h3>
       <div id="comments-placeholder">
            <p><em>Comments are enabled. (You need to set up GitHub Discussions/Giscus for comments to appear).</em></p>
       </div>
    </div>
    """

    # 3. Write Content (British English)
    prompt = f"""
    Write a Professional British English Review for '{topic}'.
    
    - **Front Matter:**
      - title: "{topic} (UK Guide {CURRENT_YEAR})"
      - date: {datetime.date.today()}
      - tags: ["Reviews", "Home"] (Add a tag relevant to the topic category for the tiles page)
    
    - **Content:**
      1. Professional Intro.
      2. **Important:** Do NOT write a markdown comparison table. I will insert the widget automatically.
      3. Detailed Mini-Reviews for the 10 products listed below.
      4. Buying Guide.
      5. Conclusion.
    
    - **Tone:** Professional, Helpful, British spelling (Colour, Customised).
    - **Products:** {str([p['name'] for p in products])}
    """
    
    try:
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        body = response.choices[0].message.content.strip()
        
        # Cleanup if AI adds dashes
        if "---" in body: body = body.split("---", 2)[2].strip()

        # Construct Final File with Structured Data + Widgets
        final_content = f"""---
title: "{topic} (UK Guide {CURRENT_YEAR})"
date: {datetime.date.today()}
description: "Professional review of the best {topic} in the UK market."
tags: ["Reviews", "Home"]
products: {products_yaml}
---

{body}

{{{{< top10_grid >}}}}

{engagement_html}
"""
        
        filename = topic.lower().replace(" ", "-")[:50] + ".md"
        path = os.path.join(SITE_CONTENT_PATH, page_type, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(final_content)
            
        log_success()
        print(f"    ✅  PUBLISHED: {filename}")
        return True
        
    except Exception as e:
        print(f"    ❌  Error: {e}")
        return False

# ==========================================
#  🚀  MAIN CONTROL PANEL
# ==========================================
if __name__ == "__main__":
    print(f"\n--- 🤖 GOD ENGINE v6.0 (Professional UK Edition) ---")
    print("1. Manual Mode (Write 1 specific page)")
    print("2. Auto-Discovery Mode (Generate pages from a category)")
    
    mode = input("Select Mode (1/2): ")
    
    if mode == "1":
        topic = input("Enter Topic (e.g. Best Air Fryers): ")
        create_page(topic, "reviews")
        
    elif mode == "2":
        seed = input("Enter Broad Category (e.g. Kitchen Appliances): ")
        qty = int(input("How many pages? (Max 10): "))
        
        topics = generate_topic_list(seed, qty)
        print(f" 📋  Queued {len(topics)} topics...")
        time.sleep(1)
        
        for t in topics:
            success = create_page(t, "reviews")
            if not success: break
            time.sleep(3)