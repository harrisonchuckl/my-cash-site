import os
import json
import datetime
import time
import random
from openai import OpenAI
from duckduckgo_search import DDGS

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
SITE_CONTENT_PATH = "./content"
SITE_START_DATE = datetime.date(2025, 5, 20) # LAUNCH DATE
AMAZON_TAG = "yourtag-21"         # Your Amazon Associate ID

# 🔑 READ API KEY
try:
    with open("key.txt", "r") as f:
        API_KEY = f.read().strip()
    client = OpenAI(api_key=API_KEY)
except FileNotFoundError:
    print("❌ ERROR: 'key.txt' not found. Please create it.")
    exit()

# ==========================================
# 🛡️ MODULE 1: SAFETY MANAGER
# ==========================================
def check_quota():
    today = datetime.date.today()
    days_alive = (today - SITE_START_DATE).days
    
    # Define Safe Speed Limits
    if days_alive < 30: limit = 5      # Month 1
    elif days_alive < 60: limit = 10   # Month 2
    else: limit = 50                   # Month 3+

    log_file = "post_history.json"
    if not os.path.exists(log_file): history = {}
    else:
        with open(log_file, "r") as f: history = json.load(f)
    
    today_str = str(today)
    today_count = history.get(today_str, 0)
    
    print(f"📊 Daily Quota: {today_count}/{limit} | Site Age: {days_alive} days")

    if today_count >= limit:
        print(f"🛑 DAILY LIMIT REACHED. Stopping.")
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
# 🧠 MODULE 2: BRAIN (TOPIC GENERATOR)
# ==========================================
def generate_topic_list(seed_category, count=10):
    print(f"🧠 Brainstorming {count} topics for '{seed_category}'...")
    prompt = f"Generate a list of {count} specific 'Best X' product comparison titles related to '{seed_category}'. Output ONLY the list, one per line."
    response = client.chat.completions.create(
        model="gpt-4o", messages=[{"role": "user", "content": prompt}]
    )
    raw = response.choices[0].message.content.strip().split("\n")
    topics = [t.strip("- ").split(". ")[-1] for t in raw if t]
    return topics

# ==========================================
# 🔎 MODULE 3: RESEARCHER (10 PRODUCTS)
# ==========================================
def find_real_products(topic):
    print(f"   🔎 Researching 10 real products for: {topic}...")
    try:
        # We need more search data to find 10 items
        with DDGS() as ddgs:
            # We search for "best X list", "top rated X", etc. to get variety
            results1 = list(ddgs.text(f"best {topic} to buy 2025 review", max_results=5))
            results2 = list(ddgs.text(f"top 10 {topic} amazon uk", max_results=5))
            results = results1 + results2
        
        if not results: return []

        # Ask AI to extract 10 distinct names
        prompt = f"Extract 10 distinct and specific product names from these search snippets. Return ONLY a comma-separated list of names. Snippets: {str(results)}"
        
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}]
        )
        
        names = response.choices[0].message.content.split(",")
        # Ensure we have clean names and limit to 10
        cleaned_names = [n.strip() for n in names if n.strip()][:10]
        
        products = []
        for name in cleaned_names:
            link = f"https://www.amazon.co.uk/s?k={name.replace(' ', '+')}&tag={AMAZON_TAG}"
            products.append({"name": name, "link": link})
            
        return products
    except Exception as e:
        print(f"   ⚠️ Search warning: {e}")
        return []

# ==========================================
# ✍️ MODULE 4: WRITER (PAGE CREATOR)
# ==========================================
def create_page(topic, page_type="reviews"):
    if not check_quota(): return False

    real_products = find_real_products(topic) if page_type == "reviews" else []
    
    engagement_html = """
    <div class="engagement-box" style="margin-top:40px; border-top:1px solid #ddd; padding-top:20px;">
        <h3>Rate this Guide</h3>
        <div class="stars" onclick="rate(this)" style="cursor:pointer; font-size:2rem; color:#f4c542;">
            &#9734;&#9734;&#9734;&#9734;&#9734;
        </div>
        <p id="msg" style="display:none; color:green;">Thanks for voting!</p>
        <script>
            function rate(el) {
                el.innerHTML = "&#9733;&#9733;&#9733;&#9733;&#9733;";
                document.getElementById('msg').style.display='block';
                localStorage.setItem('voted_'+window.location.pathname, 'true');
            }
        </script>
        <h3>Discussion</h3>
        <p>Have a question? <a href="mailto:contact@yoursite.com?subject=Comment on {{ .Title }}">Email us</a>.</p>
    </div>
    """

    prompt = f"""
    Write a detailed Hugo Markdown {page_type} post for '{topic}'.
    - Front Matter: Title, Date, Description, Tags.
    - LIST OF 10 REAL PRODUCTS: {str(real_products)}.
    - INSTRUCTIONS: 
      1. Create a "Top 10 Quick Comparison" table at the start.
      2. Write a mini-review for ALL 10 products.
      3. For every product name, link it using the 'link' provided in the data.
    - Structure: Intro, Comparison Table, 10 Product Reviews, Buying Guide, Conclusion.
    - Append this HTML at the end: {engagement_html}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        
        filename = topic.lower().replace(" ", "-")[:50] + ".md"
        path = os.path.join(SITE_CONTENT_PATH, page_type, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
            
        log_success()
        print(f"   ✅ PUBLISHED: {filename}")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

# ==========================================
# 🚀 MAIN CONTROL PANEL
# ==========================================
if __name__ == "__main__":
    print("\n--- 🤖 GOD ENGINE ACTIVATED (10-Product Edition) ---")
    print("1. Manual Mode (Write 1 specific page)")
    print("2. Auto-Discovery Mode (Generate pages from a category)")
    
    mode = input("Select Mode (1/2): ")
    
    if mode == "1":
        topic = input("Enter Topic: ")
        create_page(topic, "reviews")
        
    elif mode == "2":
        seed = input("Enter Broad Category: ")
        qty = int(input("How many pages? (Max 10): "))
        
        topics = generate_topic_list(seed, qty)
        print(f"📋 Queued {len(topics)} topics...")
        
        for t in topics:
            success = create_page(t, "reviews")
            if not success: break
            time.sleep(2)