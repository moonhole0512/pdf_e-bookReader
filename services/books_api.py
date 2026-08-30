import logging
import urllib.parse
import re
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def lookup_google_books_by_title_volume(title: str, volume: Optional[str] = None) -> Dict[str, Any]:
    """Queries Google Books API by book title and optional volume number, supporting multilingual books."""
    if not title:
        return {"error": "Title is required", "status": 400}

    # Only restrict language to Korean if title contains Korean characters; for Japanese/foreign titles, allow all
    has_ko = bool(re.search(r'[가-힣]', title))
    query_parts = [title.strip()]
    if volume:
        query_parts.append(str(volume).strip())

    query = urllib.parse.quote(' '.join(query_parts))
    lang_param = "&langRestrict=ko" if has_ko else ""
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}{lang_param}"
    logger.info(f"Requesting Google Books API: {url}")

    try:
        response = requests.get(url, headers=HEADERS, timeout=8)
        response.raise_for_status()
        data = response.json()

        items = data.get('items', [])
        if not items:
            return {"error": "No book found", "results": [], "status": 404}

        results = []
        for item in items:
            info = item.get('volumeInfo', {})
            identifiers = info.get('industryIdentifiers', [])
            isbn_13 = next((i['identifier'] for i in identifiers if i.get('type') == 'ISBN_13'), None)
            isbn_10 = next((i['identifier'] for i in identifiers if i.get('type') == 'ISBN_10'), None)

            results.append({
                "title": info.get('title'),
                "author": ", ".join(info.get('authors', [])),
                "thumbnail": info.get('imageLinks', {}).get('thumbnail'),
                "isbn_13": isbn_13,
                "isbn_10": isbn_10
            })

        return {"results": results, "status": 200}
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            logger.warning(f"Google Books API rate limited (429) for {url}")
            return {"error": "Google Books API 쿼터 한도 초과 (잠시 후 다시 시도해주세요)", "results": [], "status": 429}
        logger.error(f"Google Books API HTTP error: {e}")
        return {"error": str(e), "results": [], "status": e.response.status_code if e.response is not None else 500}
    except requests.exceptions.Timeout:
        logger.error(f"Google Books API timeout for {url}")
        return {"error": "Google Books API request timed out", "results": [], "status": 504}
    except Exception as e:
        logger.error(f"Google Books API request error: {e}")
        return {"error": str(e), "results": [], "status": 500}

def lookup_google_books_by_isbn(isbn: str) -> Dict[str, Any]:
    """Queries Google Books API by ISBN."""
    if not isbn:
        return {"error": "ISBN is required", "status": 400}

    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    logger.info(f"Requesting Google Books API with ISBN: {url}")

    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        data = response.json()

        items = data.get('items', [])
        if not items:
            return {"error": "Book not found for ISBN", "status": 404}

        info = items[0].get('volumeInfo', {})
        result = {
            "title": info.get('title'),
            "author": ", ".join(info.get('authors', [])),
            "thumbnail": info.get('imageLinks', {}).get('thumbnail'),
            "alt_images": []
        }
        return {"result": result, "status": 200}
    except requests.exceptions.Timeout:
        logger.error(f"Google Books API timeout for ISBN: {isbn}")
        return {"error": "API request timed out", "status": 504}
    except Exception as e:
        logger.error(f"Google Books API error: {e}")
        return {"error": str(e), "status": 500}
