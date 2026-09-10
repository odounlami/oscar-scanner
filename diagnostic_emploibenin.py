import requests

URL = "https://www.emploibenin.com/recherche-jobs-benin/informatique"

HEADERS_LIST = [
    (
        "minimal",
        {
            "User-Agent": "Mozilla/5.0 OscarJobScanner/1.0",
        },
    ),
    (
        "browser",
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        },
    ),
]

for name, headers in HEADERS_LIST:
    print(f"\n=== TEST {name} ===")
    try:
        with requests.Session() as session:
            response = session.get(URL, headers=headers, timeout=25, allow_redirects=True)
            print("status:", response.status_code)
            print("final_url:", response.url)
            print("server:", response.headers.get("server"))
            print("content-type:", response.headers.get("content-type"))
            print("content-length:", len(response.content))
            print("set-cookie:", bool(response.headers.get("set-cookie")))
            print("body_start:", response.text[:500].replace("\n", " "))
    except Exception as exc:
        print(type(exc).__name__, exc)
