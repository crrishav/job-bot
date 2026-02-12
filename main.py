import sys
import os
import feedparser
import time
import requests
import sqlite3
import re
from datetime import datetime

# --- CONFIGURATION (Edit these) ---
# Tip: Use an environment variable for the Webhook in production
WEBHOOK_URL = "Your webhook"
RSS_URL = "https://www.reddit.com/r/SmallBusiness+Entrepreneur+Restaurateurs+Construction+forhire+Design_Critique+startups+webdev+BusinessDesign+ecommerce+sweatystartup/new/.rss"
DB_FILE = "leads_memory.db"
CHECK_INTERVAL = 90 # Seconds

# --- FILTERING LOGIC ---
KEYWORDS = {
    "STACK": ["react", "frontend", "landing page", "website", "tailwind", "web dev", "site", "ui/ux", "javascript", "nextjs", "shopify"],
    "INTENT": ["hiring", "need", "looking for", "help", "recommend", "create", "build", "redesign", "responsive", "developer", "freelance", "budget"],
    "PAIN_POINTS": ["wix is too expensive", "shopify too expensive", "scammed", "get more customers", "lost money", "website slow", "broken site", "slow load"],
    "NEGATIVES": [
        "hiring me", "for hire", "portfolio", "intern", "junior looking", 
        "offering my services", "revenue share", "low budget", "$5", "$10", "hire me"
    ]
}

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS posts (id TEXT PRIMARY KEY, timestamp DATETIME)')
    conn.commit()
    conn.close()

def is_new(post_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM posts WHERE id=?', (post_id,))
    exists = c.fetchone()
    if not exists:
        c.execute('INSERT INTO posts (id, timestamp) VALUES (?, ?)', (post_id, datetime.now()))
        conn.commit()
    conn.close()
    return not exists

# --- LOGIC & SCORING ---
def analyze_lead(title, summary):
    content = f"{title} {summary}".lower()
    
    # 1. Instant Rejection
    if any(neg in content for neg in KEYWORDS["NEGATIVES"]):
        return None, 0

    score = 0
    tags = []

    # 2. Check Pain Points (High Value)
    for prob in KEYWORDS["PAIN_POINTS"]:
        if prob in content:
            score += 50
            tags.append("🚨 CRITICAL PROBLEM")

    # 3. Check Intent & Stack
    intent_matches = [i for i in KEYWORDS["INTENT"] if i in content]
    stack_matches = [s for s in KEYWORDS["STACK"] if s in content]
    
    score += (len(intent_matches) * 10)
    score += (len(stack_matches) * 15)

    # 4. Final Classification
    if score >= 50:
        return "🔥 HIGH QUALITY LEAD", score
    elif score >= 25:
        return "✅ POTENTIAL GIG", score
    
    return None, 0

def scan_reddit():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning for opportunities...")
    
    headers = {'User-Agent': 'LeadHunterV2/1.0 (Educational Tool)'}
    feed = feedparser.parse(RSS_URL, agent=headers['User-Agent'])
    
    for entry in feed.entries:
        if is_new(entry.id):
            clean_summary = re.sub('<.*?>', '', entry.summary)
            label, score = analyze_lead(entry.title, clean_summary)
            
            if label:
                # Color logic: Red for high score, Green for standard
                color = 15418782 if score >= 50 else 3066993
                
                payload = {
                    "embeds": [{
                        "title": f"{label} (Score: {score})",
                        "description": f"**{entry.title}**\n\n{clean_summary[:500]}...",
                        "url": entry.link,
                        "color": color,
                        "fields": [
                            {"name": "Action", "value": f"[View Post]({entry.link})", "inline": True},
                            {"name": "Subreddit", "value": entry.tags[0].term if hasattr(entry, 'tags') else "Unknown", "inline": True}
                        ],
                        "footer": {"text": "LeadHunter Pro • Be fast, be helpful."}
                    }]
                }
                requests.post(WEBHOOK_URL, json=payload)
                print(f"Match Sent: {entry.title} (Score: {score})")

if __name__ == "__main__":
    init_db()
    while True:
        try:
            scan_reddit()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(CHECK_INTERVAL)
