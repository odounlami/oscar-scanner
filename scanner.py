import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from sources import SOURCES

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ENABLE_REJECTED_NOTIFICATIONS = os.getenv("ENABLE_REJECTED_NOTIFICATIONS", "true").lower() == "true"
SEEN_FILE = "seen_posts.json"
MAX_AGE_DAYS = 14
BACKFILL_MODE = os.getenv("BACKFILL_MODE", "false").lower() == "true"
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
    value = unicodedata.normalize("NFKD", clean(value).lower())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def parse_date(value):
    if not value:
        return None
    value = clean(value).lower()
    months = {
        "janvier": "01", "janv": "01", "février": "02", "fevrier": "02", "févr": "02", "fevr": "02",
        "mars": "03", "avril": "04", "avr": "04", "mai": "05", "juin": "06",
        "juillet": "07", "juil": "07", "août": "08", "aout": "08", "aoû": "08",
        "septembre": "09", "sept": "09", "octobre": "10", "oct": "10", "novembre": "11", "nov": "11",
        "décembre": "12", "decembre": "12", "déc": "12", "dec": "12",
    }
    for name, number in sorted(months.items(), key=lambda item: len(item[0]), reverse=True):
        value = re.sub(rf"\b{re.escape(name)}\.?\b", number, value)
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %m %Y"):
        try:
            return datetime.strptime(value[:10], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", value)
    if match:
        try:
            return datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def fetch_soup(url):
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 OscarJobScanner/1.0"},
        timeout=25,
    )
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
        added = re.search(r"Date d'ajout\s*:?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{4})", text, re.I)
        deadline = re.search(r"Date limite\s*:?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{4})", text, re.I)
        reference = re.search(r"Réf\s*:\s*([A-Za-z0-9_-]+)", text, re.I)
        return {
            "published": parse_date(added.group(1)) if added else None,
            "date_limite": parse_date(deadline.group(1)) if deadline else None,
            "reference": reference.group(1) if reference else None,
            "detail_text": text,
        }
    except Exception as exc:
        print(f"[JobBenin] détail inaccessible: {type(exc).__name__}: {exc}")
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
        details = card.select_one(".job-contant p:nth-of-type(2)")
        city_node = details.select_one(".fa-city") if details else None
        diploma_node = details.select_one(".fa-user-graduate") if details else None
        city = clean(city_node.parent.get_text(" ")) if city_node else ""
        diploma = clean(diploma_node.parent.get_text(" ")) if diploma_node else ""
        location = node_value(card, [".job-contant p:nth-of-type(1)"])
        salary = node_value(card, [".jobs-amount .amount"])
        summary = detail["detail_text"] or clean(card.get_text(" "))
        jobs.append({
            "title": title, "link": link, "source": "JobBenin",
            "ville": city or location, "diplome": diploma, "salaire": salary,
            "published": detail["published"], "date_limite": detail["date_limite"],
            "reference": detail["reference"], "date_inconnue": detail["published"] is None,
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
        jobs.append({
            "title": title, "link": href, "source": "EmploiBenin",
            "ville": node_value(card, [".ville", ".city", ".field-name-field-offre-region", "[class*=region]"]) or ("Cotonou" if "cotonou" in text.lower() else ""),
            "diplome": node_value(card, [".diplome", ".education", "[class*=etude]", "[class*=diplome]"]),
            "salaire": node_value(card, [".salaire", ".salary", "[class*=salaire]"]),
            "published": published, "date_limite": None, "reference": None,
            "date_inconnue": published is None, "summary": text[:1000],
        })
        seen.add(href)
    return jobs


def extract_goafrica(soup, url):
    """Extract Go Africa Online offers from the real offer-card structure."""
    jobs, seen = [], set()
    title_links = soup.select("a[href*='/bj/emploi/job-']")

    for title_node in title_links:
        title = clean(title_node.get_text(" "))
        href = title_node.get("href")
        if len(title) < 5 or not href:
            continue
        link = urljoin(url, href)
        if link in seen:
            continue

        card = title_node.find_parent("div", class_=lambda classes: classes and "shadow-leo" in classes)
        if card is None:
            current = title_node
            for _ in range(8):
                current = current.parent if current.parent else None
                if current is None:
                    break
                text = clean(current.get_text(" "))
                if "Posté le" in text and len(text) <= 4000:
                    card = current
                    break
                if len(text) > 4000:
                    break
        if card is None:
            continue

        text = clean(card.get_text(" | "))
        posted = re.search(r"Posté le\s+([^|]+)", text, re.I)
        published = parse_date(posted.group(1)) if posted else None
        parts = [part.strip() for part in text.split(" | ") if part.strip()]

        location = ""
        for part in parts:
            if re.search(r"\b(Cotonou|Abomey-Calavi|Porto-Novo|Parakou|Ouidah|Bohicon|Abomey|Sèmè|Seme|Allada|Lokossa|Natitingou|Djougou)\b", part, re.I):
                location = part
                break

        company = ""
        if posted:
            marker = next((i for i, part in enumerate(parts) if re.search(r"Posté le\s+", part, re.I)), -1)
            if marker >= 0 and marker + 1 < len(parts):
                company = parts[marker + 1]

        jobs.append({
            "title": title, "link": link, "source": "GoAfricaOnline",
            "ville": location, "diplome": "", "salaire": "",
            "published": published, "date_limite": None, "reference": None,
            "date_inconnue": published is None, "company": company,
            "summary": text[:5000],
        })
        seen.add(link)
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
        jobs.append({
            "title": title, "link": href, "source": source, "ville": "", "diplome": "", "salaire": "",
            "published": published, "date_limite": None, "reference": None,
            "date_inconnue": published is None, "summary": text[:1000],
        })
        seen.add(href)
    return jobs


def extract_jobs(config):
    source = config["name"]
    url = config["url"]
    soup = fetch_soup(url)
    extractor = config.get("extractor", "generic")
    extractors = {
        "jobbenin": extract_jobbenin,
        "emploibenin": extract_emploibenin,
        "goafrica": extract_goafrica,
        "generic": lambda current_soup, current_url: extract_generic(current_soup, source, current_url),
    }
    return extractors.get(extractor, extractors["generic"])(soup, url)


def is_recent(job):
    published = job.get("published")
    if not published:
        return False
    now = datetime.now(timezone.utc)
    return now - timedelta(days=MAX_AGE_DAYS) <= published <= now + timedelta(days=1)


def post_id(job):
    if job.get("reference"):
        key = f"{job['source']}:{job['reference']}"
    else:
        key = "|".join([
            job.get("source", ""), normalize(job.get("title", "")),
            normalize(job.get("ville", "")), normalize(job.get("salaire", "")),
            normalize(job.get("summary", ""))[:1500],
            job["published"].strftime("%Y-%m-%d") if job.get("published") else "",
        ])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def gemini_classify(job):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY manquante")

    prompt = f'''Tu es un recruteur spécialisé dans les profils développeur web/IT au Bénin.

Analyse réellement cette annonce. Évalue : métier et missions, technologies (notamment Angular, React, Laravel, API/REST, JavaScript, front/back), expérience, localisation, diplôme, salaire, date limite et éventuels critères bloquants.

Barème : 9-10 excellente correspondance ; 7-8.9 bonne ; 6-6.9 acceptable ; 4-5.9 faible ; 0-3.9 très mauvaise/autre métier.
Score >= 6 = qualifiée.

Ne fournis pas de chaîne de pensée. Retourne uniquement les conclusions vérifiables.

JSON exact :
{{"score": number, "qualifie": boolean, "raison": "1 à 3 phrases", "points_forts": ["..."], "points_faibles": ["..."]}}

Titre: {job["title"]}
Ville: {job.get("ville", "")}
Diplôme: {job.get("diplome", "")}
Salaire: {job.get("salaire", "")}
Date de publication: {job["published"].strftime("%d/%m/%Y") if job.get("published") else ""}
Date limite: {job["date_limite"].strftime("%d/%m/%Y") if job.get("date_limite") else ""}
Détails: {job.get("summary", "")}'''

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
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=15,
    ).raise_for_status()


def source_header(source):
    return f"━━━━━━━━━━━━━━━━━━━━\n📡 <b>{source}</b>\n━━━━━━━━━━━━━━━━━━━━"


def format_job(job, result):
    date = job["published"].strftime("%d/%m/%Y") if job.get("published") else "inconnue"
    deadline = job["date_limite"].strftime("%d/%m/%Y") if job.get("date_limite") else "non précisée"
    location = f"\n🏙 Ville : {job['ville']}" if job.get("ville") else ""
    strengths = result.get("points_forts", [])
    weaknesses = result.get("points_faibles", [])
    return (
        f"💼 <b>OFFRE D’EMPLOI</b>\n\n📌 {job['title']}\n"
        f"📅 Publication : {date}\n⏳ Date limite : {deadline}{location}\n"
        f"📡 Source : {job['source']}\n\n🤖 <b>Score Gemini : {result['score']}/10</b>\n"
        f"🧠 <b>Pourquoi :</b> {result.get('raison', 'Non précisée')}\n\n"
        f"✅ <b>Points forts :</b>\n" + "\n".join(f"• {x}" for x in strengths) +
        (("\n\n⚠️ <b>Points faibles :</b>\n" + "\n".join(f"• {x}" for x in weaknesses)) if weaknesses else "") +
        f"\n\n🔗 {job['link']}"
    )


def format_rejected(job, result):
    date = job["published"].strftime("%d/%m/%Y") if job.get("published") else "inconnue"
    strengths = result.get("points_forts", [])
    weaknesses = result.get("points_faibles", [])
    return (
        f"🗑 <b>REJETÉ</b>\n\n📌 {job['title']}\n📅 {date}\n📡 Source : {job['source']}\n"
        f"🤖 <b>Score Gemini : {result['score']}/10</b>\n🧠 <b>Pourquoi :</b> {result.get('raison', 'Non précisée')}\n\n"
        f"❌ <b>Points faibles :</b>\n" + "\n".join(f"• {x}" for x in weaknesses) +
        (("\n\n✅ <b>Points forts :</b>\n" + "\n".join(f"• {x}" for x in strengths)) if strengths else "") +
        f"\n\n🔗 {job['link']}"
    )


def main():
    active = [source for source in SOURCES if source.get("active", False)]
    print(
        f"🔍 Scanner lancé | sources actives: {len(active)} | "
        f"backfill: {BACKFILL_MODE} | rejected: {ENABLE_REJECTED_NOTIFICATIONS} | Gemini: {GEMINI_MODEL}"
    )

    seen = load_seen()
    run_ids = set()
    total = 0
    source_results = []

    for config in active:
        source = config["name"]
        source_total = 0
        source_new = 0
        source_status = "ok"

        try:
            jobs = extract_jobs(config)
            recent = [job for job in jobs if is_recent(job)]
            print(f"→ {source}: {len(jobs)} annonces, {len(recent)} dans la fenêtre")
            source_total = len(recent)

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
                    if result["qualifie"]:
                        send(format_job(job, result))
                    elif ENABLE_REJECTED_NOTIFICATIONS:
                        send(format_rejected(job, result))
                    else:
                        print(f"↪️ Rejetée sans notification: {job['title']}")
                except Exception as exc:
                    print(f"⚠️ Traitement échoué ({source}): {job['title']} — {type(exc).__name__}: {exc}")
                    continue

                # Only mark an offer as seen after its processing/notification succeeded.
                seen.add(pid)
                source_new += 1
                total += 1

        except Exception as exc:
            source_status = f"erreur: {type(exc).__name__}"
            print(f"❌ {source}: {type(exc).__name__}: {exc}")

        source_results.append((source, source_status, source_total, source_new))

    # Send one clear status message per source, even when there are no new offers.
    # This is deliberately sent after the offers so the run ends with a compact recap.
    for source, status, recent_count, new_count in source_results:
        if status == "ok":
            if new_count:
                message = f"{source_header(source)}\n🆕 <b>{new_count} nouvelle(s) offre(s) envoyée(s)</b>\n🔎 {recent_count} offre(s) récentes détectée(s)."
            else:
                message = f"{source_header(source)}\nℹ️ <b>Aucune nouvelle offre.</b>\n🔎 {recent_count} offre(s) récentes déjà traitée(s)."
        else:
            message = f"{source_header(source)}\n❌ <b>Source inaccessible.</b>\nℹ️ {status}"
        send(message)

    save_seen(seen)
    send(f"\n✅ <b>SCAN TERMINÉ</b>\n💼 {total} nouvelle(s) annonce(s) analysée(s) par Gemini.")
    print(f"Terminé: {total}")


if __name__ == "__main__":
    main()
