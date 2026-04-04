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
        if (w1 not in STOPWORDS and w2 not in STOPWORDS
                and len(w1) > 3 and len(w2) > 3):
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
        with httpx.Client(headers=HEADERS, timeout=12, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Try multiple class names Indian Kanoon uses
        result_divs = (
            soup.find_all("div", class_="result_title") or
            soup.find_all("div", class_="result") or
            soup.find_all("div", class_="judgments")
        )

        # Also try finding all links inside result containers
        if not result_divs:
            result_divs = soup.find_all("div", id=lambda x: x and x.startswith("res_"))

        for div in result_divs[:max_results]:
            # Try finding the link
            a_tag = div.find("a")
            if not a_tag:
                continue

            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if not href:
                continue
            link = BASE_URL + href if href.startswith("/") else href

            # Try multiple ways to get snippet
            snippet = ""
            # Check sibling or parent for snippet text
            parent = div.find_parent("div")
            if parent:
                for cls in ["result_text", "snippet", "headnote"]:
                    snippet_div = parent.find("div", class_=cls)
                    if snippet_div:
                        snippet = snippet_div.get_text(separator=" ", strip=True)[:400]
                        break

            # If still no snippet, get text from div itself
            if not snippet:
                snippet = div.get_text(separator=" ", strip=True)[:400]
                # Remove the title from snippet
                snippet = snippet.replace(title, "").strip()[:300]

            found_keywords = extract_keywords_from_text(snippet, top_n=6) if snippet else []

            if title and len(title) > 5:
                results.append({
                    "title": title,
                    "link": link,
                    "snippet": snippet,
                    "source": "Indian Kanoon",
                    "keywords": found_keywords,
                })

        print(f"[Scraper] Found {len(results)} results for: {query}")

    except Exception as e:
        print(f"[Scraper] Error fetching Indian Kanoon: {e}")

    return results