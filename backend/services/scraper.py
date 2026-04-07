import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote
from collections import Counter

BASE_URL = "https://indiankanoon.org"
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


def extract_keywords_from_text(text: str, top_n: int = 15) -> list:
    text_clean = re.sub(r'[^a-zA-Z\s]', ' ', text.lower())
    words = text_clean.split()
    meaningful = [w for w in words if len(w) > 4 and w not in STOPWORDS]
    bigrams = []
    for i in range(len(words) - 1):
        w1, w2 = words[i], words[i + 1]
        if w1 not in STOPWORDS and w2 not in STOPWORDS and len(w1) > 3 and len(w2) > 3:
            bigrams.append(f"{w1} {w2}")
    word_counts = Counter(meaningful)
    bigram_counts = Counter(bigrams)
    combined = {}
    for w, count in word_counts.most_common(40):
        combined[w] = count
    for bg, count in bigram_counts.most_common(30):
        if count >= 1:
            combined[bg] = count * 2
    sorted_keywords = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    return [kw for kw, _ in sorted_keywords[:top_n]]


def scrape_indian_kanoon(query: str, max_results: int = 5) -> list:
    url = f"{BASE_URL}/search/?formInput={quote(query)}"
    results = []

    try:
        with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        found = []

        # Strategy 1: result_title divs
        title_divs = soup.find_all("div", class_="result_title")
        if title_divs:
            for title_div in title_divs[:max_results]:
                a_tag = title_div.find("a")
                if not a_tag:
                    continue
                title = a_tag.get_text(strip=True)
                href = a_tag.get("href", "")
                if not href or len(title) < 5:
                    continue
                link = BASE_URL + href if href.startswith("/") else href
                snippet = ""
                outer = title_div.find_parent("div")
                if outer:
                    for cls in ["result_text", "snippet"]:
                        rt = outer.find("div", class_=cls)
                        if rt:
                            snippet = rt.get_text(separator=" ", strip=True)[:400]
                            break
                found.append((title, link, snippet))

        # Strategy 2: any /doc/ links if strategy 1 found nothing
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
                    snippet = parent.get_text(separator=" ", strip=True)
                    snippet = snippet.replace(title, "").strip()[:400]
                found.append((title, link, snippet))
                if len(found) >= max_results:
                    break

        print(f"[Scraper] Found {len(found)} results for: {query}")

        for title, link, snippet in found[:max_results]:
            found_keywords = extract_keywords_from_text(snippet, top_n=6) if snippet else []
            results.append({
                "title": title,
                "link": link,
                "snippet": snippet,
                "source": "Indian Kanoon",
                "keywords": found_keywords,
            })

    except Exception as e:
        print(f"[Scraper] Error fetching Indian Kanoon: {e}")

    return results


def get_suggested_keywords(query: str) -> list:
    results = scrape_indian_kanoon(query, max_results=3)
    all_text = " ".join([r["snippet"] for r in results if r["snippet"]])
    if not all_text.strip():
        return []
    keywords = extract_keywords_from_text(all_text, top_n=12)
    return [{"keyword": kw} for kw in keywords]


def search_by_keyword(keyword: str, max_results: int = 5) -> list:
    return scrape_indian_kanoon(keyword, max_results)