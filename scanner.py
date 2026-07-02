import feedparser
import requests
import json
import os
import hashlib
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen_posts.json"


# ─────────────────────────────
# 🎯 SIGNAUX BUSINESS LOCAUX
# ─────────────────────────────

SIGNALS = [
    "ouverture", "ouvre", "nouveau", "opening", "lancement",
    "restaurant", "café", "bar", "snack", "maquis",
    "salon", "coiffure", "spa", "boutique",
    "entreprise", "startup", "agence",
    "recrute", "recrutement", "cherche"
]


# ─────────────────────────────
# 📡 SOURCES
# ─────────────────────────────

GOOGLE_NEWS_RSS = [
    ("Bénin business", "https://news.google.com/rss/search?q=ouverture+restaurant+B%C3%A9nin&hl=fr&gl=FR&ceid=FR:fr"),
    ("Côte d'Ivoire business", "https://news.google.com/rss/search?q=nouveau+restaurant+Abidjan&hl=fr&gl=FR&ceid=FR:fr"),
    ("Business Afrique", "https://news.google.com/rss/search?q=nouvelle+entreprise+Afrique+de+l%27Ouest&hl=fr&gl=FR&ceid=FR:fr"),
]


# ─────────────────────────────
# 🧠 UTILS
# ─────────────────────────────

def load_seen():
    if os.path.exists(SEEN_FILE):
        return set(json.load(open(SEEN_FILE)))
    return set()


def save_seen(seen):
    json.dump(list(seen), open(SEEN_FILE, "w"))


def post_id(entry):
    return hashlib.md5(
        (entry.get("link", "") + entry.get("title", "")).encode()
    ).hexdigest()


def is_business_signal(text):
    t = text.lower()
    return any(s in t for s in SIGNALS)


# ─────────────────────────────
# 📲 TELEGRAM
# ─────────────────────────────

def send(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configuré")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    })


# ─────────────────────────────
# 🚀 SCAN
# ─────────────────────────────

def scan(name, url, seen):
    feed = feedparser.parse(url)
    print(f"→ {name} : {len(feed.entries)} posts")

    found = 0

    for e in feed.entries:
        pid = post_id(e)
        if pid in seen:
            continue

        text = f"{e.get('title','')} {e.get('summary','')}"

        if is_business_signal(text):
            msg = (
                f"🎯 <b>Prospect détecté</b>\n\n"
                f"📌 {e.get('title','')}\n\n"
                f"🔗 {e.get('link','')}\n"
                f"📡 {name}"
            )
            send(msg)
            found += 1

        seen.add(pid)

    return found


# ─────────────────────────────
# 🧾 MAIN
# ─────────────────────────────

if __name__ == "__main__":
    print("\n🔍 Scanner lancé", datetime.now())

    send("🚀 Scanner lancé\nRecherche de prospects en cours...")

    seen = load_seen()
    total = 0

    for name, url in GOOGLE_NEWS_RSS:
        total += scan(name, url, seen)

    save_seen(seen)

    if total == 0:
        send("⚠️ Scan terminé\nAucun prospect détecté aujourd’hui.")
    else:
        send(f"✅ Scan terminé\n🎯 {total} prospect(s) trouvé(s)")

    print("Terminé:", total)
