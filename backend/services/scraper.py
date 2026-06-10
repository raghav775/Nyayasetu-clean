import os
import re
import json
import hashlib
import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote
from collections import Counter
from datetime import datetime, timedelta

BASE_URL = "https://indiankanoon.org"
COMMONLII_URL = "https://www.commonlii.org"
CACHE_TTL_HOURS = 24

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "that", "this", "it", "its", "he", "she", "they",
    "we", "you", "his", "her", "their", "our", "also", "as", "not", "no",
    "so", "if", "any", "all", "shall", "may", "would", "could", "should",
    "under", "into", "upon", "will", "which", "such", "said", "per", "vs",
    "mr", "mrs", "dr", "hon", "learned", "therefore", "whereas", "hereby",
    "therein", "thereof", "wherein", "herein", "above", "below", "court",
    "case", "order", "date", "section", "act", "para", "page", "fact",
    "time", "year", "day", "held", "view", "matter", "than", "then",
    "after", "before", "when", "where", "there", "here", "who", "what",
    "how", "been", "being", "having", "doing", "made", "make", "take",
    "taken", "given", "give", "same", "other", "another", "each", "every",
    "between", "among", "against", "without", "within", "about", "through"
}


# ─── Keyword extraction ───────────────────────────────────────────────────────

def extract_keywords_from_text(text: str, top_n: int = 15) -> list:
    text_clean = re.sub(r'[^a-zA-Z\s]', ' ', text.lower())
    words = text_clean.split()
    meaningful = [w for w in words if len(w) > 4 and w not in STOPWORDS]
    bigrams = []
    for i in range(len(words) - 1):
        w1, w2 = words[i], words[i + 1]
        if w1 not in STOPWORDS and w2 not in STOPWORDS and len(w1) > 3 and len(w2) > 3:
            bigrams.append(f"{w1} {w2}")
    combined = {}
    for w, count in Counter(meaningful).most_common(40):
        combined[w] = count
    for bg, count in Counter(bigrams).most_common(30):
        if count >= 1:
            combined[bg] = count * 2
    sorted_kw = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    return [kw for kw, _ in sorted_kw[:top_n]]


# ─── Cache helpers ────────────────────────────────────────────────────────────

def _query_hash(query: str) -> str:
    return hashlib.sha256(query.lower().strip().encode()).hexdigest()


def _get_cache(db, query: str):
    if db is None:
        return None
    try:
        from models.database import SearchCache
        cutoff = datetime.utcnow() - timedelta(hours=CACHE_TTL_HOURS)
        h = _query_hash(query)
        entry = db.query(SearchCache).filter(
            SearchCache.query_hash == h,
            SearchCache.created_at >= cutoff,
        ).first()
        if entry:
            return json.loads(entry.results_json)
    except Exception as e:
        print(f"[Cache] Read failed: {e}")
    return None


def _set_cache(db, query: str, results: list, source: str) -> None:
    if db is None or not results:
        return
    try:
        from models.database import SearchCache
        h = _query_hash(query)
        db.query(SearchCache).filter(SearchCache.query_hash == h).delete()
        db.add(SearchCache(
            query_hash=h,
            query_text=query,
            results_json=json.dumps(results, ensure_ascii=False),
            source=source,
        ))
        db.commit()
    except Exception as e:
        print(f"[Cache] Write failed: {e}")
        db.rollback()


# ─── Source 1: Indian Kanoon official API ────────────────────────────────────

def _fetch_indiankanoon_api(query: str, max_results: int, token: str) -> list:
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        response = client.post(
            "https://api.indiankanoon.org/search/",
            headers={"Authorization": f"Token {token}"},
            data={"formInput": query, "pagenum": "0"},
        )
        response.raise_for_status()
        payload = response.json()

    docs = payload.get("docs", [])
    if not isinstance(docs, list):
        return []

    results = []
    for doc in docs[:max_results]:
        tid = str(doc.get("tid") or "").strip()
        title = (doc.get("title") or "").strip()
        headline = doc.get("headline") or ""
        snippet = BeautifulSoup(headline, "html.parser").get_text(separator=" ", strip=True)[:400]
        if not tid or not title:
            continue
        keywords = extract_keywords_from_text(snippet, top_n=6)
        results.append({
            "title": title,
            "link": f"{BASE_URL}/doc/{tid}/",
            "snippet": snippet,
            "source": "Indian Kanoon",
            "keywords": keywords,
        })
    return results


# ─── Source 2: Indian Kanoon web scrape (fallback) ───────────────────────────

def _fetch_indiankanoon_scrape(query: str, max_results: int) -> list:
    url = f"{BASE_URL}/search/?formInput={quote(query)}"

    with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

    found = []

    # Strategy 1: id="res_N" divs (Indian Kanoon's actual HTML structure)
    result_divs = soup.find_all("div", id=lambda x: x and x.startswith("res_"))
    if result_divs:
        for div in result_divs[:max_results]:
            a_tag = div.find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if not href or len(title) < 5:
                continue
            link = BASE_URL + href if href.startswith("/") else href
            p_tag = div.find("p")
            snippet = p_tag.get_text(separator=" ", strip=True)[:400] if p_tag else ""
            if not snippet:
                snippet = div.get_text(separator=" ", strip=True).replace(title, "").strip()[:300]
            found.append((title, link, snippet))

    # Strategy 2: any /doc/ links
    if not found:
        seen = set()
        for a_tag in soup.find_all("a", href=lambda h: h and "/doc/" in str(h)):
            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if not title or len(title) < 5 or href in seen:
                continue
            seen.add(href)
            link = BASE_URL + href if href.startswith("/") else href
            parent = a_tag.find_parent("div")
            snippet = ""
            if parent:
                snippet = parent.get_text(separator=" ", strip=True).replace(title, "").strip()[:400]
            found.append((title, link, snippet))
            if len(found) >= max_results:
                break

    results = []
    for title, link, snippet in found[:max_results]:
        keywords = extract_keywords_from_text(snippet, top_n=6) if snippet else []
        results.append({
            "title": title,
            "link": link,
            "snippet": snippet,
            "source": "Indian Kanoon",
            "keywords": keywords,
        })
    return results


# ─── Source 3: CommonLII (second fallback) ───────────────────────────────────

def _fetch_commonlii(query: str, max_results: int) -> list:
    url = (
        f"{COMMONLII_URL}/cgi-bin/sinosrch.cgi"
        f"?method=auto&query={quote(query)}&results={max_results}&meta=/in"
    )

    with httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

    results = []
    seen = set()

    for a_tag in soup.find_all(
        "a",
        href=lambda h: h and "/in/" in str(h) and (
            "cases" in str(h) or "legis" in str(h) or "judgments" in str(h)
        ),
    ):
        href = a_tag.get("href", "")
        title = a_tag.get_text(strip=True)
        if not title or len(title) < 5 or href in seen:
            continue
        seen.add(href)
        link = href if href.startswith("http") else f"{COMMONLII_URL}{href}"

        # Snippet from next dd/p sibling of the parent container
        parent = a_tag.find_parent(["dt", "li", "div"])
        snippet = ""
        if parent:
            nxt = parent.find_next_sibling(["dd", "p"])
            if nxt:
                snippet = nxt.get_text(separator=" ", strip=True)[:400]
            if not snippet:
                snippet = parent.get_text(separator=" ", strip=True).replace(title, "").strip()[:300]

        keywords = extract_keywords_from_text(snippet, top_n=6) if snippet else []
        results.append({
            "title": title,
            "link": link,
            "snippet": snippet,
            "source": "CommonLII",
            "keywords": keywords,
        })
        if len(results) >= max_results:
            break

    return results


# ─── Main orchestrator ────────────────────────────────────────────────────────

def search_cases(query: str, max_results: int = 5, db=None) -> list:
    """
    4-tier lookup:
      1. SQLite cache (24-hour TTL)
      2. Indian Kanoon official API  (needs INDIAN_KANOON_TOKEN env var)
      3. Indian Kanoon web scrape    (fallback when API key missing/fails)
      4. CommonLII                   (last resort)
    Returns a list of result dicts (empty list if all sources fail).
    """
    # 1. Cache
    cached = _get_cache(db, query)
    if cached is not None:
        print(f"[CaseSearch] cache hit — {len(cached)} results for {query[:60]!r}")
        return cached

    token = os.getenv("INDIAN_KANOON_TOKEN", "").strip()

    # 2. Indian Kanoon API
    if token:
        try:
            results = _fetch_indiankanoon_api(query, max_results, token)
            if results:
                _set_cache(db, query, results, "ik_api")
                print(f"[CaseSearch] IK API — {len(results)} results")
                return results
            print("[CaseSearch] IK API returned 0 results, falling back")
        except Exception as e:
            print(f"[CaseSearch] IK API failed: {e}")
    else:
        print("[CaseSearch] INDIAN_KANOON_TOKEN not set, skipping API")

    # 3. Indian Kanoon scrape
    try:
        results = _fetch_indiankanoon_scrape(query, max_results)
        if results:
            _set_cache(db, query, results, "ik_scrape")
            print(f"[CaseSearch] IK scrape — {len(results)} results")
            return results
        print("[CaseSearch] IK scrape returned 0 results, falling back")
    except Exception as e:
        print(f"[CaseSearch] IK scrape failed: {e}")

    # 4. CommonLII
    try:
        results = _fetch_commonlii(query, max_results)
        if results:
            _set_cache(db, query, results, "commonlii")
            print(f"[CaseSearch] CommonLII — {len(results)} results")
            return results
        print("[CaseSearch] CommonLII returned 0 results")
    except Exception as e:
        print(f"[CaseSearch] CommonLII failed: {e}")

    print(f"[CaseSearch] all sources exhausted for {query[:60]!r}")
    return []


# ─── Backwards-compatible aliases ────────────────────────────────────────────

def scrape_indian_kanoon(query: str, max_results: int = 5) -> list:
    return search_cases(query, max_results)


def get_suggested_keywords(query: str) -> list:
    results = search_cases(query, max_results=3)
    all_text = " ".join(r.get("snippet", "") for r in results)
    if not all_text.strip():
        return []
    return [{"keyword": kw} for kw in extract_keywords_from_text(all_text, top_n=12)]


def search_by_keyword(keyword: str, max_results: int = 5) -> list:
    return search_cases(keyword, max_results)
