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
# 1. MOTS-CLÉS PROSPECTION
# ─────────────────────────────

BUSINESS_OPENING = [
    "ouvre", "ouverture", "opening", "grand opening", "inauguration",
    "nouveau restaurant", "nouvelle boutique", "nouveau magasin",
    "nouveau salon", "nouveau café", "nouveau bar",
    "lancement", "startup", "nouvelle entreprise", "nouvelle société"
]

SERVICE_REQUEST = [
    "cherche graphiste", "logo", "community manager",
    "marketing", "communication", "branding", "réseaux sociaux"
]

RECRUITMENT = [
    "recrute", "recrutement", "hiring", "cherche serveur",
    "cherche cuisinier", "cherche manager", "job",
    "emploi", "staff", "embauche"
]

LOCAL_BUSINESS = [
    "restaurant", "maquis", "fast-food", "snack", "bar",
    "café", "pizzeria", "boulangerie",
    "salon", "coiffure", "spa", "onglerie",
    "clinique", "pharmacie", "cabinet",
    "agence immobilière", "immobilier"
]

ALL_KEYWORDS = BUSINESS_OPENING + SERVICE_REQUEST + RECRUITMENT + LOCAL_BUSINESS


# ─────────────────────────────
# 2. SOURCES RSS
# ─────────────────────────────

INDEED_RSS = [
    ("Indeed dev", "https://fr.indeed.com/rss?q=d%C3%A9veloppeur+web&sort=date"),
    ("Indeed freelance", "https://fr.indeed.com/rss?q=freelance+react&sort=date"),
]

EXTRA_RSS = [
    ("Freelance Info", "https://www.freelance-informatique.fr/rss.php?type=mission"),
    ("Journal CM", "https://www.journalducm.com/feed/")
]


# ─────────────────────────────
# 3. UTILITAIRES
# ─────────────────────────────

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def post_id(entry):
    return hashlib.md5(
        (entry.get("link", "") + entry.get("title", "")).encode()
    ).hexdigest()


def clean_text(entry):
    text = f"{entry.get('title', '')} {entry.get('summary', '')} {entry.get('description', '')}"
    return text.lower()


# ─────────────────────────────
# 4. SCORING (CŒUR DU SYSTEME)
# ─────────────────────────────

def score(text):
    s = 0
    reasons = []

    def check(words, points, label):
        nonlocal s
        if any(w in text for w in words):
            s += points
            reasons.append(f"+{points} {label}")

    check(BUSINESS_OPENING, 10, "Business opening")
    check(SERVICE_REQUEST, 12, "Service demandé")
    check(RECRUITMENT, 8, "Recrutement")
    check(LOCAL_BUSINESS, 6, "Commerce local")

    return s, reasons


# ─────────────────────────────
# 5. TELEGRAM
# ─────────────────────────────

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram non configuré")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False


def format_message(entry, source, score_value, reasons):
    title = entry.get("title", "Sans titre")[:120]
    link = entry.get("link", "")
    date = entry.get("published", datetime.now().strftime("%d/%m/%Y"))

    return (
        f"🎯 <b>Prospect détecté</b>\n\n"
        f"📌 <b>{title}</b>\n\n"
        f"⭐ Score: {score_value}/30\n"
        f"{chr(10).join(reasons)}\n\n"
        f"🔗 <a href='{link}'>Voir source</a>\n"
        f"📡 {source}\n"
        f"🕐 {date}"
    )


# ─────────────────────────────
# 6. SCAN RSS
# ─────────────────────────────

def scan_feed(name, url, seen, min_score=12):
    if not url:
        return 0

    found = 0

    try:
        feed = feedparser.parse(url)
        print(f"→ {name} : {len(feed.entries)} entrées")

        for entry in feed.entries:
            pid = post_id(entry)
            if pid in seen:
                continue

            text = clean_text(entry)
            s, reasons = score(text)

            if s >= min_score:
                msg = format_message(entry, name, s, reasons)
                send_telegram(msg)
                found += 1

            seen.add(pid)

    except Exception as e:
        print(f"❌ Erreur {name}: {e}")

    return found


# ─────────────────────────────
# 7. MAIN
# ─────────────────────────────

if __name__ == "__main__":
    print(f"\n🔍 Scan démarré — {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    seen = load_seen()
    total = 0

    print("\n📡 Indeed...")
    for name, url in INDEED_RSS:
        total += scan_feed(name, url, seen)

    print("\n📡 Extra sources...")
    for name, url in EXTRA_RSS:
        total += scan_feed(name, url, seen)

    save_seen(seen)

    print(f"\n✅ Terminé — {total} prospects envoyés")
