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
    "cherche développeur", "cherche un développeur", "besoin développeur",
    "besoin d'un dev", "cherche dev web", "recherche développeur web",
    "besoin site web", "créer site web", "faire un site", "refaire site",
    "application mobile", "cherche freelance", "mission freelance",
    "développeur freelance", "dev freelance", "next.js", "react freelance",
    "looking for developer", "need a developer", "hire developer",
    "web developer needed", "freelance developer", "build website",
    "site web Bénin", "développeur Cotonou", "dev Abidjan", "site web Afrique",
    "application Dakar", "développeur Lomé",
]

GOOGLE_ALERTS_RSS = [
    os.getenv("ALERT_RSS_1", ""),
    os.getenv("ALERT_RSS_2", ""),
    os.getenv("ALERT_RSS_3", ""),
    os.getenv("ALERT_RSS_4", ""),
    os.getenv("ALERT_RSS_5", ""),
]

EXTRA_RSS = [
    "https://www.journalducm.com/feed/",
    "https://bj.jolome.com/rss/annonces.xml",
]

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
    msg = (
        f"✅ <b>Oscar Scanner — Démarrage</b>\n\n"
        f"Le scanner est actif et tourne correctement.\n"
        f"🕐 {now}\n\n"
        f"📡 Sources configurées : {sum(1 for u in GOOGLE_ALERTS_RSS if u)} Google Alerts\n"
        f"🔍 Mots-clés actifs : {len(KEYWORDS)}\n\n"
        f"Tu recevras une notif dès qu'une opportunité est détectée."
    )
    ok = send_telegram(msg)
    if ok:
        print("✅ Telegram OK — message de confirmation envoyé")
    else:
        print("❌ Telegram KO — vérifie TELEGRAM_TOKEN et TELEGRAM_CHAT_ID")
    return ok

def format_message(entry, source_name):
    title = entry.get("title", "Sans titre")[:120]
    link = entry.get("link", "")
    summary = entry.get("summary", "")[:250].replace("<b>", "").replace("</b>", "").replace("<br>", " ")
    date = entry.get("published", datetime.now().strftime("%d/%m/%Y"))
    return (
        f"🎯 <b>Nouvelle opportunité</b>\n"
        f"📌 <b>{title}</b>\n\n"
        f"📝 {summary}...\n\n"
        f"🔗 <a href='{link}'>Voir le post</a>\n"
        f"📡 Source : {source_name}\n"
        f"🕐 {date}"
    )

def scan_feed(url, source_name, seen):
    if not url:
        return 0
    found = 0
    try:
        feed = feedparser.parse(url)
        entries = feed.entries
        print(f"   → {source_name} : {len(entries)} entrée(s) trouvée(s)")
        for entry in entries:
            pid = post_id(entry)
            if pid in seen:
                continue
            text = f"{entry.get('title', '')} {entry.get('summary', '')}"
            if matches(text):
                msg = format_message(entry, source_name)
                send_telegram(msg)
                found += 1
            seen.add(pid)
    except Exception as e:
        print(f"   ❌ Erreur sur {source_name} : {e}")
    return found

if __name__ == "__main__":
    print(f"\n🔍 Scan démarré — {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    # Test Telegram au démarrage
    telegram_ok = test_telegram()
    if not telegram_ok:
        print("⚠️  Arrêt — Telegram non fonctionnel")
        exit(1)

    seen = load_seen()
    total = 0

    alerts = [
        ("cherche développeur web", os.getenv("ALERT_RSS_1", "")),
        ("besoin site web freelance", os.getenv("ALERT_RSS_2", "")),
        ("mission dev Afrique", os.getenv("ALERT_RSS_3", "")),
        ("next.js react freelance", os.getenv("ALERT_RSS_4", "")),
        ("développeur Cotonou Bénin", os.getenv("ALERT_RSS_5", "")),
    ]

    print(f"\n📡 Scan des Google Alerts...")
    for name, url in alerts:
        total += scan_feed(url, f"Google Alerts — {name}", seen)

    print(f"\n📡 Scan des sources extra...")
    for url in EXTRA_RSS:
        total += scan_feed(url, url.split("/")[2], seen)

    save_seen(seen)
    print(f"\n✅ Scan terminé — {total} nouvelle(s) opportunité(s) envoyée(s)")
