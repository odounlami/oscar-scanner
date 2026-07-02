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

KEYWORDS = [
    # Français
    "cherche développeur", "cherche un développeur", "besoin développeur",
    "besoin d'un dev", "cherche dev web", "recherche développeur web",
    "besoin site web", "créer site web", "faire un site", "refaire site",
    "application mobile", "cherche freelance", "mission freelance",
    "développeur freelance", "dev freelance", "next.js", "react freelance",
    "développeur react", "développeur next", "intégrateur web",
    # Anglais
    "looking for developer", "need a developer", "hire developer",
    "web developer needed", "freelance developer", "build website",
    "react developer", "next.js developer", "frontend developer",
    # Contexte local
    "site web Bénin", "développeur Cotonou", "dev Abidjan", "site web Afrique",
    "application Dakar", "développeur Lomé", "développeur Afrique",
]

# ─── Sources RSS Indeed (immédiates, pas de délai) ────────────────────────────
INDEED_RSS = [
    ("Indeed — dev web freelance FR",     "https://fr.indeed.com/rss?q=d%C3%A9veloppeur+web+freelance&sort=date"),
    ("Indeed — next.js react freelance",  "https://fr.indeed.com/rss?q=next.js+react+freelance&sort=date"),
    ("Indeed — dev web remote",           "https://fr.indeed.com/rss?q=d%C3%A9veloppeur+web+remote&sort=date"),
    ("Indeed — mission freelance react",  "https://fr.indeed.com/rss?q=mission+freelance+react&sort=date"),
    ("Indeed — intégrateur web",          "https://fr.indeed.com/rss?q=int%C3%A9grateur+web+freelance&sort=date"),
]

# ─── Sources RSS supplémentaires ──────────────────────────────────────────────
EXTRA_RSS = [
    ("Freelance-Informatique",  "https://www.freelance-informatique.fr/rss.php?type=mission&techno=react"),
    ("Freelance-Informatique",  "https://www.freelance-informatique.fr/rss.php?type=mission&techno=next"),
    ("Journal du CM",           "https://www.journalducm.com/feed/"),
]

# ─── Google Alerts RSS (optionnel, se peuple avec le temps) ───────────────────
GOOGLE_ALERTS_RSS = [
    ("Google Alerts 1", os.getenv("ALERT_RSS_1", "")),
    ("Google Alerts 2", os.getenv("ALERT_RSS_2", "")),
    ("Google Alerts 3", os.getenv("ALERT_RSS_3", "")),
    ("Google Alerts 4", os.getenv("ALERT_RSS_4", "")),
    ("Google Alerts 5", os.getenv("ALERT_RSS_5", "")),
]

# ─── Utilitaires ──────────────────────────────────────────────────────────────

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def post_id(entry):
    return hashlib.md5((entry.get("link", "") + entry.get("title", "")).encode()).hexdigest()

def matches(text):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in KEYWORDS)

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  Telegram non configuré")
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
        print(f"❌ Erreur Telegram : {e}")
        return False

def test_telegram():
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    sources_actives = len(INDEED_RSS) + len(EXTRA_RSS) + sum(1 for _, u in GOOGLE_ALERTS_RSS if u)
    msg = (
        f"✅ <b>Oscar Scanner — Démarrage</b>\n\n"
        f"🕐 {now}\n"
        f"📡 {sources_actives} sources actives\n"
        f"🔍 {len(KEYWORDS)} mots-clés surveillés\n\n"
        f"Sources : Indeed FR, Freelance-Informatique, Google Alerts\n\n"
        f"Tu recevras une notif dès qu'une opportunité est détectée."
    )
    ok = send_telegram(msg)
    if ok:
        print("✅ Telegram OK")
    else:
        print("❌ Telegram KO — vérifie TELEGRAM_TOKEN et TELEGRAM_CHAT_ID")
    return ok

def format_message(entry, source_name):
    title = entry.get("title", "Sans titre")[:120]
    link = entry.get("link", "")
    summary = entry.get("summary", "")[:300].replace("<b>", "").replace("</b>", "").replace("<br>", " ")
    date = entry.get("published", datetime.now().strftime("%d/%m/%Y"))
    return (
        f"🎯 <b>Nouvelle opportunité</b>\n"
        f"📌 <b>{title}</b>\n\n"
        f"📝 {summary}...\n\n"
        f"🔗 <a href='{link}'>Voir le post</a>\n"
        f"📡 Source : {source_name}\n"
        f"🕐 {date}"
    )

def scan_feed(name, url, seen):
    if not url:
        return 0
    found = 0
    try:
        feed = feedparser.parse(url)
        entries = feed.entries
        print(f"   → {name} : {len(entries)} entrée(s)")
        for entry in entries:
            pid = post_id(entry)
            if pid in seen:
                continue
            text = f"{entry.get('title', '')} {entry.get('summary', '')}"
            if matches(text):
                msg = format_message(entry, name)
                send_telegram(msg)
                found += 1
            seen.add(pid)
    except Exception as e:
        print(f"   ❌ Erreur {name} : {e}")
    return found

# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n🔍 Scan démarré — {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    telegram_ok = test_telegram()
    if not telegram_ok:
        print("⚠️  Arrêt — Telegram non fonctionnel")
        exit(1)

    seen = load_seen()
    total = 0

    print(f"\n📡 Indeed RSS...")
    for name, url in INDEED_RSS:
        total += scan_feed(name, url, seen)

    print(f"\n📡 Sources freelance...")
    for name, url in EXTRA_RSS:
        total += scan_feed(name, url, seen)

    print(f"\n📡 Google Alerts...")
    for name, url in GOOGLE_ALERTS_RSS:
        total += scan_feed(name, url, seen)

    save_seen(seen)
    print(f"\n✅ Scan terminé — {total} nouvelle(s) opportunité(s) envoyée(s)")
