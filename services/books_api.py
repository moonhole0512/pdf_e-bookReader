import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def lookup_google_books_by_title_volume(title: str, volume: Optional[str] = None) -> Dict[str, Any]:
    """Queries Google Books API by book title and optional volume number."""
    if not title:
        return {"error": "Title is required", "status": 400}

    processed_title = title.replace(' ', '')
    query_parts = [processed_title]
    if volume:
        query_parts.append(volume)

    query = f"\"{' '.join(query_parts)}\""
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&langRestrict=ko"
    logger.info(f"Requesting Google Books API: {url}")

    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        data = response.json()

        items = data.get('items', [])
        if not items:
            return {"error": "No book found", "status": 404}

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
    except requests.exceptions.Timeout:
        logger.error(f"Google Books API timeout for {url}")
        return {"error": "Google Books API request timed out", "status": 504}
    except Exception as e:
        logger.error(f"Google Books API request error: {e}")
        return {"error": str(e), "status": 500}

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
