import os
from openai import OpenAI

# --- CONFIGURATION ---
# Read API Key from the safe file
try:
    with open("key.txt", "r") as f:
        API_KEY = f.read().strip()
except FileNotFoundError:
    print("❌ Error: 'key.txt' file not found. Please create it and paste your API key inside.")
    exit()

client = OpenAI(api_key=API_KEY)

def create_page(topic, page_type):
    print(f"🤖 Generating {page_type} for: {topic}...")

    # UPDATED PROMPTS FOR 10 PRODUCTS + ADS + SUMMARY
    prompts = {
        "reviews": f"""
        Write a comprehensive 'Best 10 {topic}' guide in Hugo Markdown.
        
        STRUCTURE:
        1. Front Matter: title, date, type='reviews'.
        2. Introduction: Why this product category matters.
        3. Product Reviews: Review 10 distinct products. 
           - FOR EACH PRODUCT use this shortcode format exactly: 
             {{< amazon name='PRODUCT NAME' link='#' image='PLACEHOLDER' price='Under £XXX' >}}
           - Follow the shortcode with a 2-paragraph review (Pros/Cons).
           - INSERT the shortcode {{< ad >}} after Product #3 and Product #7.
        4. Buying Guide: What to look for when buying {topic}.
        5. Conclusion & Top Picks: Create a "Winner's Podium" section summarizing:
           - "Best Budget Pick"
           - "Best Mid-Range Pick"
           - "Best Premium Pick"
        """,
        
        "directory": f"Write a directory listing for '{topic}'. Front matter: title, date, type='directory'. List 10 fictional local businesses with phone numbers. Insert {{< ad >}} after the 5th listing.",
        
        "recipes": f"Write a recipe for '{topic}'. Front matter: title, date, type='recipes'. Ingredients & Steps. Insert {{< ad >}} after step 3."
    }

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompts[page_type]}]
        )
        content = response.choices[0].message.content
        
        # Clean up Markdown formatting
        content = content.replace("```markdown", "").replace("```", "")
        
        # Save File
        filename = topic.lower().replace(" ", "-") + ".md"
        filepath = os.path.join("content", page_type, filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"✅ Success! Saved to {filepath}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

# --- MENU ---
print("\n--- 10-PRODUCT AI GENERATOR ---")
print("1. Create a Review (10 Products + Ads)")
print("2. Create a Directory")
print("3. Create a Recipe")
choice = input("Enter number (1-3): ")
topic = input("Enter Topic (e.g. 'Best Cordless Vacuums'): ")

if choice == "1": create_page(topic, "reviews")
elif choice == "2": create_page(topic, "directory")
elif choice == "3": create_page(topic, "recipes")