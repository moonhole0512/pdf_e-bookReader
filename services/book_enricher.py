import re
import urllib.parse
import logging
import requests
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def clean_book_title(raw_title: str) -> str:
    """Removes volume numbers, file extension, and trailing noise from title for searching."""
    t = raw_title.strip()
    t = re.sub(r'\.pdf$', '', t, flags=re.I)
    t = re.sub(r'[\s_-]*Special$', '', t, flags=re.I)
    t = re.sub(r'[\s_-]*0*\d+(?:\.\d+)?$', '', t)
    return t.strip()

def has_korean(text: str) -> bool:
    """Checks if text contains any Hangul syllables."""
    return bool(re.search(r'[가-힣]', text))

def is_exact_volume_match(candidate_title: str, target_vol: Optional[int]) -> bool:
    """
    Strict volume matcher.
    Ensures that if target_vol is 1, it does NOT accidentally match '11', '16', '2', etc.
    """
    if target_vol is None or target_vol <= 0:
        return True

    # 1. Reject if an explicit conflicting volume suffix is found (e.g. 11권, 16권, 2권)
    explicit_vols = re.findall(r'(?<!\d)(\d+)(?:권|부|탄|화|집)', candidate_title)
    if explicit_vols:
        if int(explicit_vols[0]) != target_vol:
            return False
        return True

    # 2. Look for standalone integer matches (e.g. "제목 1", "제목 (1)", "제목! 1")
    all_numbers = [int(n) for n in re.findall(r'(?<!\d)(\d+)(?!\d)', candidate_title)]
    valid_vols = [n for n in all_numbers if n < 1900] # Ignore publication years

    if target_vol in valid_vols:
        # Check if a higher number like 11 or 16 is also present alongside 1
        # e.g., "나와 호랑이님 16" should not match target_vol=1
        if target_vol == 1:
            higher_vols = [n for n in valid_vols if n > 1]
            if higher_vols and target_vol not in explicit_vols:
                # If there's 16 and target is 1 without explicit "1권", it's likely volume 16
                return False
        return True

    # Volume 1 fallback: If candidate title matches base title perfectly without any volume number
    if target_vol == 1 and not valid_vols:
        return True

    return False

def parse_aladin_search_results(html: str, clean_title: str, target_vol: Optional[int]) -> List[Dict[str, Any]]:
    """Parses all item boxes from Aladin HTML search page."""
    boxes = html.split('class="ss_book_box"')[1:]
    candidates = []

    # Normalize by stripping all whitespace and non-alphanumeric/non-cjk symbols
    norm_base = re.sub(r'[^\w가-힣a-zA-Z0-9\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+', '', clean_title).lower()
    # Normalize Kanji variance: 畵 <-> 画
    norm_base = norm_base.replace('画', '畵')

    for box in boxes:
        # Title
        t_match = re.search(r'<a[^>]+class=["\']bo3["\'][^>]*>(.*?)</a>', box, re.DOTALL)
        if not t_match:
            continue
        cand_title = re.sub(r'<[^>]+>', '', t_match.group(1)).strip()
        norm_cand = re.sub(r'[^\w가-힣a-zA-Z0-9\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+', '', cand_title).lower()
        norm_cand = norm_cand.replace('画', '畵')

        # Relevance check
        if len(norm_base) <= 3:
            if not re.search(rf'(?:^|[\s\[(]){re.escape(clean_title)}(?:[\s\]):!?~-]|\d|$)', cand_title, re.I):
                continue
        else:
            if norm_base not in norm_cand and norm_cand not in norm_base:
                continue

        # Check volume match strictly
        if not is_exact_volume_match(cand_title, target_vol):
            continue

        # Cover Image
        img_match = re.search(r'<img[^>]+src=["\'](https?://image\.aladin\.co\.kr/product/[^"\'\s>]+)["\']', box)
        cover_url = None
        isbn = None
        if img_match:
            raw_cover = img_match.group(1)
            # Upgrade cover to high-resolution 500px cover
            cover_url = re.sub(r'/cover\d*/', '/cover500/', raw_cover)
            isbn_m = re.search(r'/cover\w*/([a-zA-Z0-9]+)_\d+\.', raw_cover)
            if isbn_m:
                isbn = isbn_m.group(1)

        # Author
        author = "알 수 없음"
        li_matches = re.findall(r'<li>(.*?)</li>', box, re.DOTALL)
        for li in li_matches:
            clean_li = re.sub(r'<[^>]+>', '', li).strip()
            if '|' in clean_li and not any(k in clean_li for k in ['배송', '마일리지', '세일', '정가', '소득공제']):
                parts = clean_li.split('|')
                author = re.sub(r'\([^)]*\)', '', parts[0].strip()).strip()
                break

        # Score candidate
        score = 50
        if norm_base == norm_cand:
            score += 30
        if cover_url:
            score += 20

        candidates.append({
            "title": cand_title,
            "author": author,
            "cover_url": cover_url,
            "isbn": isbn,
            "score": score,
            "source": "aladin"
        })

    candidates.sort(key=lambda c: c['score'], reverse=True)
    return candidates

def fetch_aladin_metadata(title: str, volume: Optional[int] = None, author_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Searches Aladin with title, volume, and optional author hint."""
    clean_t = clean_book_title(title)
    is_foreign = not has_korean(clean_t)
    
    # Priority targets: Book first for Korean titles, Foreign/All for non-Korean
    targets = ["Foreign", "All"] if is_foreign else ["Book", "All"]

    search_terms = []
    if author_hint and author_hint not in ("Unknown", "알 수 없음"):
        # Use first author if multiple
        primary_author = author_hint.split(',')[0].strip()
        search_terms.append(f"{clean_t} {primary_author} {volume}" if volume else f"{clean_t} {primary_author}")
    if volume and volume > 0:
        search_terms.append(f"{clean_t} {volume}")
        search_terms.append(f"{clean_t} {volume}권")
    search_terms.append(clean_t)

    for target in targets:
        for term in search_terms:
            encoded = urllib.parse.quote(term)
            url = f"https://www.aladin.co.kr/search/wsearchresult.aspx?SearchTarget={target}&SearchWord={encoded}"
            try:
                r = requests.get(url, headers=HEADERS, timeout=6)
                if r.status_code == 200:
                    candidates = parse_aladin_search_results(r.text, clean_t, volume)
                    if candidates:
                        return candidates[0]
            except Exception as e:
                logger.debug(f"Aladin search error for '{term}': {e}")

    return None

def fetch_google_books_metadata(title: str, volume: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Fallback to Google Books API if Aladin cannot find the book."""
    clean_t = clean_book_title(title)
    query = f"\"{clean_t}\" {volume}" if volume else f"\"{clean_t}\""
    url = f"https://www.googleapis.com/books/v1/volumes?q={urllib.parse.quote(query)}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            for item in data.get('items', [])[:3]:
                info = item.get('volumeInfo', {})
                cand_title = info.get('title', '')
                if not is_exact_volume_match(cand_title, volume):
                    continue

                thumb = info.get('imageLinks', {}).get('thumbnail')
                if thumb and thumb.startswith('http://'):
                    thumb = 'https://' + thumb[7:]
                authors = ", ".join(info.get('authors', [])) or "알 수 없음"
                identifiers = info.get('industryIdentifiers', [])
                isbn = next((i['identifier'] for i in identifiers if 'ISBN' in i.get('type', '')), None)

                return {
                    "title": cand_title,
                    "author": authors,
                    "cover_url": thumb,
                    "isbn": isbn,
                    "score": 40,
                    "source": "google_books"
                }
    except Exception as e:
        logger.debug(f"Google books fallback failed for '{title}': {e}")
    return None

def enrich_book_info(title: str, volume: Optional[int] = None, author_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Main entry point for smart multi-source book metadata enrichment.
    Prioritizes high-res Aladin metadata and falls back to Google Books.
    """
    # 1. Try Aladin
    meta = fetch_aladin_metadata(title, volume, author_hint)
    if meta:
        return meta

    # 2. Try Google Books Fallback
    meta = fetch_google_books_metadata(title, volume)
    if meta:
        return meta

    return None

import threading
import time

class LibraryEnricher:
    """
    Background batch metadata enricher for whole library.
    Searches missing covers and authors with zero UI blocking.
    """
    _lock = threading.Lock()
    _is_running = False
    _status = {
        "state": "idle",
        "message": "준비 완료",
        "total_books": 0,
        "processed_books": 0,
        "updated_files": 0,
        "current_title": "",
        "start_time": None,
        "duration_seconds": 0
    }

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        with cls._lock:
            s = cls._status.copy()
            if cls._is_running and s.get("start_time"):
                s["duration_seconds"] = round(time.time() - s["start_time"], 1)
            return s

    @classmethod
    def start_enrichment(cls, app, force_all: bool = False) -> bool:
        with cls._lock:
            if cls._is_running:
                return False
            cls._is_running = True
            cls._status = {
                "state": "running",
                "message": "온라인 도서 정보 검색 중...",
                "total_books": 0,
                "processed_books": 0,
                "updated_files": 0,
                "current_title": "",
                "start_time": time.time(),
                "duration_seconds": 0
            }

        thread = threading.Thread(
            target=cls._run_enrich_thread,
            args=(app, force_all),
            daemon=True
        )
        thread.start()
        return True

    @classmethod
    def _run_enrich_thread(cls, app, force_all: bool):
        from models import db, Book, File

        with app.app_context():
            start_t = time.time()
            try:
                query = Book.query
                if not force_all:
                    # Target books missing cover or author
                    query = query.filter((Book.cover_url == None) | (Book.author == None) | (Book.author == 'Unknown'))

                books_to_process = query.all()
                total = len(books_to_process)

                with cls._lock:
                    cls._status["total_books"] = total

                updated_files_count = 0

                for idx, book in enumerate(books_to_process, 1):
                    with cls._lock:
                        cls._status["processed_books"] = idx
                        cls._status["current_title"] = book.title

                    known_author = book.author if book.author not in (None, 'Unknown') else None
                    first_cover = book.cover_url

                    for f in book.files:
                        if not force_all and f.cover_url and f.author:
                            continue

                        meta = enrich_book_info(book.title, volume=f.volume_number, author_hint=known_author)
                        if meta:
                            if not known_author and meta.get('author') not in (None, '알 수 없음', 'Unknown'):
                                known_author = meta['author']
                            if not first_cover and meta.get('cover_url'):
                                first_cover = meta['cover_url']

                            f.title = meta.get('title') or f.title
                            f.author = meta.get('author') or f.author
                            if meta.get('cover_url'):
                                f.cover_url = meta['cover_url']

                            updated_files_count += 1
                            with cls._lock:
                                cls._status["updated_files"] = updated_files_count

                        time.sleep(0.1) # Courteous rate limit

                    if known_author:
                        book.author = known_author
                    if first_cover:
                        book.cover_url = first_cover

                    db.session.commit()

                duration = round(time.time() - start_t, 1)
                with cls._lock:
                    cls._is_running = False
                    cls._status["state"] = "completed"
                    cls._status["duration_seconds"] = duration
                    cls._status["message"] = f"정보 자동 완성 완료: {updated_files_count}개 파일 갱신 ({duration}초 소요)"

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error in batch library enrichment: {e}", exc_info=True)
                with cls._lock:
                    cls._is_running = False
                    cls._status["state"] = "error"
                    cls._status["message"] = f"오류 발생: {str(e)}"

