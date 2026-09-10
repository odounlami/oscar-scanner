import json
import os
import re
import hashlib
import unicodedata
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ENABLE_REJECTED_NOTIFICATIONS = os.getenv("ENABLE_REJECTED_NOTIFICATIONS", "true").lower() == "true"
SEEN_FILE = "seen_posts.json"
MAX_AGE_DAYS = 14
BACKFILL_MODE = os.getenv("BACKFILL_MODE", "false").lower() == "true"
EMPLOIBENIN_URL = "https://www.emploibenin.com/recherche-jobs-benin/informatique"
JOBBENIN_URL = "https://jobbenin.com/index.php/offres/categorie/informatique"
SOURCES = [("EmploiBenin", EMPLOIBENIN_URL), ("JobBenin", JOBBENIN_URL)]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


def load_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def clean(value):
    return re.sub(r"\s+", " ", BeautifulSoup(value or "", "html.parser").get_text(" ")).strip()


def normalize(value):
    value = clean(value).lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def parse_date(value):
    if not value:
        return None
    value = clean(value).lower()
    months = {"janvier":"01", "février":"02", "fevrier":"02", "mars":"03", "avril":"04", "mai":"05", "juin":"06", "juillet":"07", "août":"08", "aout":"08", "septembre":"09", "octobre":"10", "novembre":"11", "décembre":"12", "decembre":"12"}
    for name, number in months.items():
        value = value.replace(name, number)
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %m %Y"):
        try:
            return datetime.strptime(value[:10], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", value)
    if match:
        try:
            return datetime(*map(int, (match.group(3), match.group(2), match.group(1))), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def fetch_soup(url):
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 OscarJobScanner/1.0"}, timeout=25)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def node_value(node, selectors):
    for selector in selectors:
        found = node.select_one(selector)
        if found:
            return clean(found.get("datetime") or found.get_text(" "))
    return ""


def extract_jobbenin_detail(link):
    try:
        soup = fetch_soup(link)
        text = clean(soup.get_text(" "))
        added_match = re.search(r"Date d'ajout\s*:?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{4})", text, re.I)
        deadline_match = re.search(r"Date limite\s*:?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{4})", text, re.I)
        reference_match = re.search(r"Réf\s*:\s*([A-Za-z0-9_-]+)", text, re.I)
        return {
            "published": parse_date(added_match.group(1)) if added_match else None,
            "date_limite": parse_date(deadline_match.group(1)) if deadline_match else None,
            "reference": reference_match.group(1) if reference_match else None,
            "detail_text": text,
        }
    except Exception as exc:
        print(f"[JobBenin] détail inaccessible {link}: {type(exc).__name__}: {exc}")
        return {"published": None, "date_limite": None, "reference": None, "detail_text": ""}


def extract_jobbenin(soup, url):
    jobs = []
    for card in soup.select(".job-bx"):
        title_node = card.select_one(".job-contant h4 a")
        if not title_node:
            continue

        title = clean(title_node.get_text(" "))
        href = title_node.get("href")
        if len(title) < 3 or not href:
            continue

        link = urljoin(url, href)
        detail = extract_jobbenin_detail(link)
        published = detail["published"]
        location = node_value(card, [".job-contant p:nth-of-type(1)"])
        details = card.select_one(".job-contant p:nth-of-type(2)")
        city = ""
        diploma = ""
        city_node = details.select_one(".fa-city") if details else None
        diploma_node = details.select_one(".fa-user-graduate") if details else None
        if city_node:
            city = clean(city_node.parent.get_text(" "))
        if diploma_node:
            diploma = clean(diploma_node.parent.get_text(" "))
        salary = node_value(card, [".jobs-amount .amount"])
        summary = detail["detail_text"] or clean(card.get_text(" "))

        jobs.append({
            "title": title,
            "link": link,
            "source": "JobBenin",
            "ville": city or location,
            "diplome": diploma,
            "salaire": salary,
            "published": published,
            "date_limite": detail["date_limite"],
            "reference": detail["reference"],
            "date_inconnue": published is None,
            "summary": summary[:5000],
        })
    return jobs


def extract_emploibenin(soup, url):
    jobs, seen = [], set()
    cards = soup.select("article, .views-row, .job-listing, .list-offer, .offre, .offer, .job-item")
    for card in cards:
        link = card.select_one("a[href]")
        title_node = card.select_one("h1, h2, h3, h4, .title, .job-title, .offer-title, .views-field-title")
        if not link or not title_node:
            continue
        title = clean(title_node.get_text(" "))
        href = urljoin(url, link.get("href"))
        if len(title) < 8 or href in seen:
            continue
        text = clean(card.get_text(" "))
        published = parse_date(node_value(card, ["time", ".date", ".job-date", ".date-posted", "[class*=date]"]) or text)
        jobs.append({"title": title, "link": href, "source": "EmploiBenin", "ville": node_value(card, [".ville", ".city", ".field-name-field-offre-region", "[class*=region]"]) or ("Cotonou" if "cotonou" in text.lower() else ""), "diplome": node_value(card, [".diplome", ".education", "[class*=etude]", "[class*=diplome]"]), "salaire": node_value(card, [".salaire", ".salary", "[class*=salaire]"]), "published": published, "date_limite": None, "reference": None, "date_inconnue": published is None, "summary": text[:1000]})
        seen.add(href)
    return jobs


def extract_generic(soup, source, url):
    jobs, seen = [], set()
    for link in soup.select("a[href]"):
        title = clean(link.get_text(" "))
        href = urljoin(url, link.get("href"))
        if len(title) < 8 or href in seen or href.startswith("javascript:"):
            continue
        parent = link
        for _ in range(4):
            if not parent.parent:
                break
            candidate = parent.parent
            candidate_text = clean(candidate.get_text(" "))
            if len(candidate_text) > 2500:
                break
            parent = candidate
        text = clean(parent.get_text(" "))
        if len(text) < len(title) + 10:
            continue
        published = parse_date(node_value(parent, ["time", ".date", ".job-date", ".date-posted", "[class*=date]"]) or text)
        seen.add(href)
        jobs.append({"title": title, "link": href, "source": source, "ville": "", "diplome": "", "salaire": "", "published": published, "date_limite": None, "reference": None, "date_inconnue": published is None, "summary": text[:1000]})
    return jobs


def extract_jobs(source, url):
    soup = fetch_soup(url)
    if source == "JobBenin":
        return extract_jobbenin(soup, url)
    if source == "EmploiBenin":
        return extract_emploibenin(soup, url)
    return extract_generic(soup, source, url)


def is_recent(job):
    if not job.get("published"):
        return False
    now = datetime.now(timezone.utc)
    return now - timedelta(days=MAX_AGE_DAYS) <= job["published"] <= now + timedelta(days=1)


def post_id(job):
    if job.get("reference"):
        key = f"{job['source']}:{job['reference']}"
    else:
        key = "|".join([
            job.get("source", ""),
            normalize(job.get("title", "")),
            normalize(job.get("ville", "")),
            normalize(job.get("salaire", "")),
            normalize(job.get("summary", ""))[:1500],
            job["published"].strftime("%Y-%m-%d") if job.get("published") else "",
        ])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def gemini_classify(job):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY manquante")
    prompt = f'''Tu es un recruteur spécialisé dans les profils développeur web/IT au Bénin.

Analyse réellement cette annonce avant de lui attribuer un score. Ne te contente pas de repérer des mots-clés.
Évalue notamment :
1. adéquation du métier et des missions avec un profil développeur web/IT ;
2. adéquation des technologies et compétences demandées (notamment Angular, React, Laravel, API/REST, JavaScript, front-end/back-end) ;
3. niveau d'expérience demandé par rapport à un profil junior/intermédiaire ;
4. localisation et contexte au Bénin ;
5. diplôme et autres exigences obligatoires ;
6. salaire lorsqu'il est indiqué ;
7. date limite et actualité de l'offre ;
8. pénalités importantes si l'offre vise clairement un autre métier, exige un niveau manifestement incompatible ou impose une compétence bloquante très éloignée du profil.

Le score doit refléter ton jugement global :
- 9-10 : excellente correspondance, offre clairement à cibler ;
- 7-8.9 : bonne correspondance, quelques réserves ;
- 6-6.9 : correspondance acceptable mais plusieurs réserves ;
- 4-5.9 : faible correspondance ;
- 0-3.9 : très mauvaise correspondance / autre métier.

Score >= 6 = qualifiée.

Tu dois faire l'analyse en interne, mais ne fournis PAS de raisonnement détaillé étape par étape ni de chaîne de pensée. Retourne uniquement les conclusions utiles et vérifiables qui expliquent le score.

Réponds uniquement en JSON valide avec exactement ces champs :
- score : nombre de 0 à 10
- qualifie : true ou false
- raison : explication concise de 1 à 3 phrases, directement liée aux éléments de l'annonce
- points_forts : tableau de 1 à 4 éléments
- points_faibles : tableau de 0 à 4 éléments

Annonce à analyser :
Titre: {job["title"]}
Ville: {job.get("ville", "")}
Diplôme: {job.get("diplome", "")}
Salaire: {job.get("salaire", "")}
Date de publication: {job["published"].strftime("%d/%m/%Y") if job.get("published") else ""}
Date limite: {job["date_limite"].strftime("%d/%m/%Y") if job.get("date_limite") else ""}
Détails de l'annonce: {job.get("summary", "")}'''
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": GEMINI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        timeout=30,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text[:500].replace("\n", " ")
        raise RuntimeError(f"Gemini {response.status_code}: {detail}") from exc
    result = json.loads(response.json()["candidates"][0]["content"]["parts"][0]["text"])
    result["score"] = float(result.get("score", 0))
    result["qualifie"] = result["score"] >= 6
    return result


def send(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configuré")
        return
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False}, timeout=15).raise_for_status()


def format_job(job, result):
    date = job["published"].strftime("%d/%m/%Y") if job.get("published") else "date_inconnue"
    deadline = job["date_limite"].strftime("%d/%m/%Y") if job.get("date_limite") else "non précisée"
    extra = f"\n🏙 Ville : {job['ville']}" if job.get("ville") else ""
    strengths = result.get("points_forts", [])
    weaknesses = result.get("points_faibles", [])
    return f"💼 <b>OFFRE D’EMPLOI</b>\n\n📌 {job['title']}\n📅 Publication : {date}\n⏳ Date limite : {deadline}{extra}\n📡 Source : {job['source']}\n\n🤖 <b>Score Gemini : {result['score']}/10</b>\n🧠 <b>Pourquoi :</b> {result.get('raison', 'Non précisée')}\n\n✅ <b>Points forts :</b>\n" + "\n".join(f"• {item}" for item in strengths) + ("\n\n⚠️ <b>Points faibles :</b>\n" + "\n".join(f"• {item}" for item in weaknesses) if weaknesses else "") + f"\n\n🔗 {job['link']}"


def format_rejected(job, result):
    date = job["published"].strftime("%d/%m/%Y") if job.get("published") else "date_inconnue"
    strengths = result.get("points_forts", [])
    weaknesses = result.get("points_faibles", [])
    return f"🗑 <b>REJETÉ</b>\n\n📌 {job['title']}\n📅 {date}\n📡 Source : {job['source']}\n🤖 <b>Score Gemini : {result['score']}/10</b>\n🧠 <b>Pourquoi :</b> {result.get('raison', 'Non précisée')}\n\n❌ <b>Points faibles :</b>\n" + "\n".join(f"• {item}" for item in weaknesses) + ("\n\n✅ <b>Points forts :</b>\n" + "\n".join(f"• {item}" for item in strengths) if strengths else "") + f"\n\n🔗 {job['link']}"


def main():
    print(f"🔍 Scanner lancé | backfill: {BACKFILL_MODE} | rejected: {ENABLE_REJECTED_NOTIFICATIONS} | Gemini: {GEMINI_MODEL}")
    seen, total = load_seen(), 0
    run_ids = set()
    for source, url in SOURCES:
        try:
            jobs = extract_jobs(source, url)
            recent = [job for job in jobs if is_recent(job)]
            print(f"→ {source}: {len(jobs)} annonces, {len(recent)} dans la fenêtre")
            for job in recent:
                pid = post_id(job)
                if pid in run_ids:
                    print(f"↪️ Doublon dans le run: {job['title']}")
                    continue
                run_ids.add(pid)
                if not BACKFILL_MODE and pid in seen:
                    continue
                try:
                    result = gemini_classify(job)
                except Exception as exc:
                    print(f"⚠️ Classification échouée ({source}): {job['title']} — {type(exc).__name__}: {exc}")
                    continue
                if result["qualifie"]:
                    send(format_job(job, result))
                elif ENABLE_REJECTED_NOTIFICATIONS:
                    send(format_rejected(job, result))
                seen.add(pid)
                total += 1
        except Exception as exc:
            print(f"❌ {source}: {type(exc).__name__}: {exc}")
    save_seen(seen)
    send(f"✅ Terminé\n💼 {total} annonces analysées par Gemini")
    print(f"Terminé: {total}")


if __name__ == "__main__":
    main()
