import re
import urllib.parse
import logging
import requests
from html import unescape
from typing import Dict, Any, Optional, List
from services.categories import normalize_app_category

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

CATEGORY_UNCLASSIFIED = "미분류"

def extract_aladin_subject_category_path(html: str) -> List[str]:
    """Extract Aladin's hierarchical subject path, not its mixed JSON-LD tag list."""
    category_list = re.search(
        r'<ul[^>]+id=["\']ulCategory["\'][^>]*>(.*?)</ul>', html, re.I | re.S
    )
    if not category_list:
        return []

    path = []
    for label in re.findall(r'<a\b[^>]*>(.*?)</a>', category_list.group(1), re.I | re.S):
        label = unescape(re.sub(r'<[^>]+>', '', label)).strip()
        if label and label not in ('접기', '펼치기') and label not in path:
            path.append(label)
    return path

def choose_aladin_primary_category(path: List[str]) -> Optional[str]:
    """Choose the usable genre level and discard store root plus collection/imprint leaf."""
    levels = [label for label in path if label not in ('국내도서', '외국도서', '전자책', 'eBook')]
    if not levels:
        return None
    # Aladin paths are usually: broad shelf > genre > collection/imprint.
    # The second level retains useful distinctions (e.g. 라이트 노벨, 일본소설, 심리학).
    return levels[1] if len(levels) >= 2 else levels[0]

def fetch_aladin_product_categories(product_url: Optional[str]) -> Dict[str, Optional[str]]:
    """Fetch a stable primary category and the provider's complete subject path."""
    if not product_url:
        return {'source_category': None, 'category': None}
    try:
        response = requests.get(product_url, headers=HEADERS, timeout=6)
        if response.status_code == 200:
            path = extract_aladin_subject_category_path(response.text)
            return {
                'source_category': ' > '.join(path) or None,
                'category': normalize_app_category(
                    choose_aladin_primary_category(path),
                    ' > '.join(path),
                )
            }
    except Exception as exc:
        logger.debug("Aladin subject classification lookup failed for %s: %s", product_url, exc)
    return {'source_category': None, 'category': None}

def clean_book_title(raw_title: str) -> str:
    """
    Removes volume numbers, file extension, brackets, publisher labels, and trailing noise from title for searching.
    Handles Japanese fullwidth punctuation (！？), parentheses (コミック), and labels.
    """
    t = raw_title.strip()
    t = re.sub(r'\.pdf$', '', t, flags=re.I)
    t = re.sub(r'[\s_-]*Special$', '', t, flags=re.I)
    # Remove publisher/format brackets at the end: (ジャンプコミックス)(コミック), [コミック], 【...】
    t = re.sub(r'(?:[\(\[（【《〈][^\)\]）】》〉]*(?:コミック|コミックス|文庫|ノベル|판형|스캔|완결|정발|단행본|comic|manga)[^\)\]）】》〉]*[\)\]）】》〉])+\s*$', '', t, flags=re.I)
    t = t.strip()
    # Remove trailing volume expressions: !?1, !？ 1, 01, 01巻, 1권, 第1巻, Vol.1, etc.
    t = re.sub(r'[!！？?\s_-]*(?:(?:제|第)?\s*0*\d+(?:\.\d+)?\s*(?:권|巻|화|탄|부|vol(?:\.|\b))?\s*)+$', '', t, flags=re.I)
    t = re.sub(r'[\s_-]*0*\d+(?:\.\d+)?\s*$', '', t)
    # If trailing brackets still remain (e.g. (1), (2)), strip them
    t = re.sub(r'[\(\[（【《〈]\s*0*\d+\s*[\)\]）】》〉]\s*$', '', t)
    return t.strip()

def isbn_10_to_13(isbn_10: str) -> str:
    """Converts a 10-digit ISBN to a standard 13-digit EAN/ISBN with recalculating checksum."""
    clean_10 = re.sub(r'[-\s]', '', isbn_10)
    if len(clean_10) != 10 or not clean_10[:9].isdigit():
        return isbn_10
    core = "978" + clean_10[:9]
    checksum = sum(int(digit) * (1 if i % 2 == 0 else 3) for i, digit in enumerate(core))
    check_digit = (10 - (checksum % 10)) % 10
    return core + str(check_digit)

def isbn_13_to_10(isbn_13: str) -> Optional[str]:
    """Converts a standard 13-digit ISBN (starting with 978) to a 10-digit ISBN."""
    clean_13 = re.sub(r'[-\s]', '', str(isbn_13 or ''))
    if len(clean_13) != 13 or not clean_13.startswith('978'):
        return clean_13 if len(clean_13) == 10 else None
    core = clean_13[3:12]
    rem = sum(int(digit) * (10 - i) for i, digit in enumerate(core)) % 11
    check_val = (11 - rem) % 11
    check_digit = 'X' if check_val == 10 else str(check_val)
    return core + check_digit

def resolve_bypass_cover_url(isbn: Optional[str]) -> Optional[str]:
    """
    Bypasses domestic adult-content / out-of-print cover restrictions (19book placeholders)
    by resolving high-resolution original covers from Amazon CDN and Google Books Direct.
    """
    if not isbn:
        return None

    clean = re.sub(r'[-\s]', '', str(isbn))
    isbn_10 = clean if len(clean) == 10 else isbn_13_to_10(clean)
    isbn_13 = clean if len(clean) == 13 else isbn_10_to_13(clean)

    # 1. Try Amazon High-Res CDN (unrestricted, full-size original cover)
    if isbn_10:
        amazon_url = f"https://images-na.ssl-images-amazon.com/images/P/{isbn_10}.09.LZZZZZZZ.jpg"
        try:
            r = requests.head(amazon_url, headers=HEADERS, timeout=3)
            if r.status_code == 200 and int(r.headers.get('content-length', 0)) > 2000:
                return amazon_url
        except Exception:
            pass

    # 2. Try Google Books Direct Thumbnail (no API key required, reliable front cover)
    if isbn_13:
        gbooks_url = f"https://books.google.com/books/content?vid=ISBN{isbn_13}&printsec=frontcover&img=1&zoom=1"
        try:
            r = requests.head(gbooks_url, headers=HEADERS, timeout=3)
            if r.status_code == 200 and int(r.headers.get('content-length', 0)) > 2000:
                return gbooks_url
        except Exception:
            pass

    return None

def has_korean(text: str) -> bool:
    """Checks if text contains any Hangul syllables."""
    return bool(re.search(r'[가-힣]', text))

def is_exact_volume_match(candidate_title: str, target_vol: Optional[int]) -> bool:
    """
    Strict volume matcher.
    Ensures that if target_vol is 1, it does NOT accidentally match '11', '16', '2', etc.
    Also ignores commemorative numbers like '20주년', '3판', '100쇄'.
    """
    if target_vol is None or target_vol <= 0:
        return True

    # Strip out non-volume numbers like '20주년', '100쇄', '제2판'
    cleaned = re.sub(r'\d+주년|\d+쇄|\d+만부|\d+만\b|제?\d+판', '', candidate_title)

    # 1. Reject if an explicit conflicting volume suffix is found (e.g. 11권, 16권, 2권)
    explicit_vols = re.findall(r'(?<!\d)(\d+)(?:권|부|탄|화|집)', cleaned)
    if explicit_vols:
        if int(explicit_vols[0]) != target_vol:
            return False
        return True

    # 2. Look for standalone integer matches (e.g. "제목 1", "제목 (1)", "제목! 1")
    all_numbers = [int(n) for n in re.findall(r'(?<!\d)(\d+)(?!\d)', cleaned)]
    valid_vols = [n for n in all_numbers if n < 1900] # Ignore publication years

    if target_vol in valid_vols:
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

def parse_aladin_search_results(html: str, clean_title: str, target_vol: Optional[int], is_isbn_query: bool = False) -> List[Dict[str, Any]]:
    """Parses all item boxes from Aladin HTML search page with strict image and genre filtering."""
    boxes = html.split('class="ss_book_box"')[1:]
    candidates = []

    clean_num = re.sub(r'[-\s]', '', clean_title)
    if not is_isbn_query:
        is_isbn_query = bool(re.fullmatch(r'\d{9}[\dX]|\d{13}', clean_num))

    # Normalize by stripping all whitespace and non-alphanumeric/non-cjk symbols
    norm_base = re.sub(r'[^\w가-힣a-zA-Z0-9\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+', '', clean_title).lower()
    norm_base = norm_base.replace('画', '畵')

    for box in boxes:
        # Title
        t_match = re.search(r'<a[^>]+class=["\']bo3["\'][^>]*>(.*?)</a>', box, re.DOTALL)
        if not t_match:
            continue
        cand_title = re.sub(r'<[^>]+>', '', t_match.group(1)).strip()
        norm_cand = re.sub(r'[^\w가-힣a-zA-Z0-9\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+', '', cand_title).lower()
        norm_cand = norm_cand.replace('画', '畵')
        product_url_match = re.search(
            r'<a[^>]+href=["\']([^"\']*wproduct\.aspx\?ItemId=\d+[^"\']*)["\'][^>]+class=["\']bo3["\']',
            box, re.I
        )
        product_url = product_url_match.group(1) if product_url_match else None

        if not is_isbn_query:
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

        # Author and publisher info. The authoritative genre is on the product detail page.
        author = "알 수 없음"
        publisher_info = ""
        li_matches = re.findall(r'<li>(.*?)</li>', box, re.DOTALL)
        for li in li_matches:
            clean_li = re.sub(r'<[^>]+>', '', li).strip()
            if '|' in clean_li and not any(k in clean_li for k in ['배송', '마일리지', '세일', '정가', '소득공제']):
                parts = clean_li.split('|')
                author = re.sub(r'\([^)]*\)', '', parts[0].strip()).strip()
                publisher_info = clean_li
                break

        # Cover Image Extraction & Direct ISBN Attribute Resolution
        box_isbn_m = re.search(r'isbn=["\']?(\d{9}[\dX]|\d{10}|\d{13})["\']?', box, re.I)
        box_item_id_m = re.search(r'itemId=["\']?(\d+)["\']?', box, re.I)
        raw_box_isbn = box_isbn_m.group(1) if box_isbn_m else None
        item_id = box_item_id_m.group(1) if box_item_id_m else None

        all_imgs = re.findall(r'https?://image\.aladin\.co\.kr/product/[^"\'\s>]+\.(?:jpg|png)', box)
        cover_url = None
        isbn = None

        # 1. Prefer explicit front covers (cover200, cover150, cover500, cover/)
        front_covers = [u for u in all_imgs if 'cover' in u.lower() and 'spineshelf' not in u.lower() and '19book' not in u.lower()]
        if front_covers:
            cover_url = re.sub(r'/cover\d*/', '/cover500/', front_covers[0])
        elif all_imgs:
            # 2. If only SpineShelf exists, convert SpineShelf/..._d.jpg to cover500/..._1.jpg
            first_img = all_imgs[0]
            if 'spineshelf' in first_img.lower():
                cover_url = re.sub(r'/SpineShelf/', '/cover500/', first_img, flags=re.I)
                cover_url = re.sub(r'_[a-zA-Z]\.jpg$', '_1.jpg', cover_url, flags=re.I)
            elif '19book' not in first_img.lower():
                cover_url = first_img

        if not isbn and raw_box_isbn:
            isbn = isbn_10_to_13(raw_box_isbn) if len(raw_box_isbn) == 10 else raw_box_isbn

        if cover_url and not isbn:
            isbn_m = re.search(r'/cover\w*/([a-zA-Z0-9]+)_\d+\.', cover_url)
            if isbn_m:
                raw_isbn = isbn_m.group(1)
                isbn = isbn_10_to_13(raw_isbn) if len(raw_isbn) == 10 else raw_isbn

        # 3. Bypass adult (19book) restrictions or missing covers using Amazon High-Res CDN
        if not cover_url or '19book' in cover_url.lower():
            bypass_url = resolve_bypass_cover_url(raw_box_isbn or isbn)
            if bypass_url:
                cover_url = bypass_url
            elif item_id and raw_box_isbn:
                prefix = item_id[:5]
                mid = item_id[5:7] if len(item_id) >= 7 else "00"
                cover_url = f"https://image.aladin.co.kr/product/{prefix}/{mid}/cover500/{raw_box_isbn}_2.jpg"

        # Scoring candidate
        score = 50
        has_explicit_target_num = False
        if target_vol:
            cleaned_title = re.sub(r'\d+주년|\d+쇄|\d+만부|\d+만\b|제?\d+판', '', cand_title)
            explicit_nums = [int(n) for n in re.findall(r'(?<!\d)(\d+)(?!\d)', cleaned_title) if int(n) < 1900]
            if target_vol in explicit_nums:
                score += 50 # Strongly favor candidate with exact target volume number!
                has_explicit_target_num = True
            elif target_vol == 1 and not explicit_nums:
                # Volume 1 original title bonus (many light novels release vol 1 without volume number)
                score += 50
                has_explicit_target_num = True

        if norm_base == norm_cand:
            score += 30 if (not target_vol or has_explicit_target_num) else 10
        elif norm_base in norm_cand:
            score += 20

        if cover_url:
            score += 20

        # Genre adjustment: prefer original novel/light novel over comic/webtoon adaptation
        comb_text = f"{cand_title} {publisher_info}".lower()
        if any(c in comb_text for c in ['(만화)', '코믹', '만화판', '앤솔로지', '코믹스', '웹툰', '웹툰비즈']):
            score -= 60
        if any(n in comb_text for n in ['라이트노벨', '소설', '문고', '문학', '노블', '시드노벨', 'seed novel', '디앤씨미디어']):
            score += 40

        candidates.append({
            "title": cand_title,
            "author": author,
            "publisher": publisher_info,
            "source_category": None,
            "category": None,
            "product_url": product_url,
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
    
    # Priority targets: Book first, then eBook for out-of-print titles, then All
    targets = ["Foreign", "eBook", "All"] if is_foreign else ["Book", "eBook", "All"]

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
            for page in [1, 2]:
                url = f"https://www.aladin.co.kr/search/wsearchresult.aspx?SearchTarget={target}&SearchWord={encoded}&page={page}"
                try:
                    r = requests.get(url, headers=HEADERS, timeout=6)
                    if r.status_code == 200:
                        candidates = parse_aladin_search_results(r.text, clean_t, volume)
                        if candidates:
                            top_cand = candidates[0]
                            categories = fetch_aladin_product_categories(top_cand.get('product_url'))
                            if categories.get('category'):
                                top_cand.update(categories)
                            if not top_cand.get('cover_url') or '19book' in top_cand.get('cover_url', '').lower():
                                bypass = resolve_bypass_cover_url(top_cand.get('isbn'))
                                if bypass:
                                    top_cand['cover_url'] = bypass
                            return top_cand
                except Exception as e:
                    logger.debug(f"Aladin search error for '{term}' p{page}: {e}")

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
                google_categories = info.get('categories', [])
                source_category = ', '.join(google_categories) or None

                return {
                    "title": cand_title,
                    "author": authors,
                    "cover_url": thumb,
                    "isbn": isbn,
                    "source_category": source_category,
                    "category": normalize_app_category(
                        google_categories[0] if google_categories else None,
                        source_category,
                    ),
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

def search_book_candidates(query: str, volume: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Searches both Aladin and Google Books for a manual lookup query,
    returning a deduplicated list of candidates for the user to choose from.
    Seamlessly handles both book titles and 10/13 digit ISBN inputs,
    and supports multi-page search for out-of-print or unnumbered volume 1 novels.
    """
    results = []
    seen_titles = set()

    clean_num = re.sub(r'[-\s]', '', query)
    is_isbn = bool(re.fullmatch(r'\d{9}[\dX]|\d{13}', clean_num))

    # 1. Search Aladin
    if is_isbn:
        search_phrases = [clean_num]
        aladin_targets = ["Book", "Foreign", "All"]
        max_pages = 1
    else:
        clean_q = clean_book_title(query)
        is_foreign = not has_korean(clean_q)
        aladin_targets = ["Foreign", "All", "Book"] if is_foreign else ["Book", "eBook", "All"]

        search_phrases = []
        # Support Kanji variants: 漫畵 <-> 漫画
        kanji_variants = [clean_q]
        if '漫畵' in clean_q:
            kanji_variants.append(clean_q.replace('漫畵', '漫画'))
        elif '漫画' in clean_q:
            kanji_variants.append(clean_q.replace('漫画', '漫畵'))

        for q_variant in kanji_variants:
            if volume and volume > 0:
                search_phrases.append(f"{q_variant} {volume}")
                search_phrases.append(q_variant) # Bare series title is crucial for finding foreign volumes
            else:
                search_phrases.append(q_variant)

        max_pages = 2 # Search up to page 2 to find out-of-print or foreign books

    for target in aladin_targets:
        for phrase in search_phrases:
            for page in range(1, max_pages + 1):
                try:
                    url = f"https://www.aladin.co.kr/search/wsearchresult.aspx?SearchTarget={target}&SearchWord={urllib.parse.quote(phrase)}&page={page}"
                    r = requests.get(url, headers=HEADERS, timeout=6)
                    if r.status_code == 200:
                        aladin_cands = parse_aladin_search_results(r.text, phrase if is_isbn else clean_q, None if is_isbn else volume, is_isbn_query=is_isbn)
                        for c in aladin_cands:
                            norm_key = f"{c['title']}_{c['author']}".lower()
                            if norm_key not in seen_titles:
                                seen_titles.add(norm_key)
                                results.append({
                                    "title": c['title'],
                                    "author": c['author'],
                                    "thumbnail": c.get('cover_url'),
                                    "isbn_13": clean_num if (is_isbn and len(clean_num) == 13) else c.get('isbn'),
                                    "isbn_10": clean_num if (is_isbn and len(clean_num) == 10) else None,
                                    "source_category": c.get('source_category'),
                                    "category": normalize_app_category(c.get('category'), c.get('source_category')),
                                    "product_url": c.get('product_url'),
                                    "score": c.get('score', 0),
                                    "source": "Aladin"
                                })
                    if is_isbn and results:
                        break
                except Exception as e:
                    logger.debug(f"Candidate search (Aladin {target} p{page}) error: {e}")
            if is_isbn and results:
                break
        if is_isbn and results:
            break

    # Sort results by score desc so original novel comes first
    results.sort(key=lambda x: x.get('score', 0), reverse=True)

    # 2. Search Google Books (Only if Aladin results are sparse to prevent 429 quota exhaustion)
    if len(results) < 3:
        try:
            search_q = clean_num if is_isbn else (f"{clean_q} {volume}" if volume else clean_q)
            lang_param = "&langRestrict=ko" if (not is_isbn and has_korean(clean_q)) else ""
            g_url = f"https://www.googleapis.com/books/v1/volumes?q={urllib.parse.quote(search_q)}{lang_param}"
            gr = requests.get(g_url, headers=HEADERS, timeout=5)
            if gr.status_code == 200:
                data = gr.json()
                for item in data.get('items', [])[:5]:
                    info = item.get('volumeInfo', {})
                    cand_t = info.get('title', '')
                    cand_auth = ", ".join(info.get('authors', [])) or "알 수 없음"
                    thumb = info.get('imageLinks', {}).get('thumbnail')
                    if thumb and thumb.startswith('http://'):
                        thumb = 'https://' + thumb[7:]

                    identifiers = info.get('industryIdentifiers', [])
                    isbn = next((i['identifier'] for i in identifiers if 'ISBN' in i.get('type', '')), None)
                    google_categories = info.get('categories', [])
                    source_category = ', '.join(google_categories) or None

                    norm_key = f"{cand_t}_{cand_auth}".lower()
                    if norm_key not in seen_titles:
                        seen_titles.add(norm_key)
                        results.append({
                            "title": cand_t,
                            "author": cand_auth,
                            "thumbnail": thumb,
                            "isbn_13": isbn,
                            "isbn_10": None,
                            "source_category": source_category,
                            "category": normalize_app_category(
                                google_categories[0] if google_categories else None,
                                source_category,
                            ),
                            "source": "Google Books"
                        })
        except Exception as e:
            logger.debug(f"Candidate search (Google) error: {e}")

    # Final pass: Ensure no candidate is left with 19+ placeholder or missing cover if Amazon CDN has it
    for r in results:
        t = r.get('thumbnail')
        if not t or '19book' in t.lower():
            bypass_t = resolve_bypass_cover_url(r.get('isbn_13') or r.get('isbn_10'))
            if bypass_t:
                r['thumbnail'] = bypass_t

    return results

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
                    # A normal enrichment also repairs old mixed JSON-LD tag values.
                    query = query.filter(
                        (Book.cover_url == None) | (Book.author == None) | (Book.author == 'Unknown') |
                        (Book.category == None) | (Book.category == CATEGORY_UNCLASSIFIED) |
                        (Book.source_category == None) | (Book.source_category == '') |
                        (Book.metadata_source.ilike('aladin') & Book.source_category.contains(','))
                    )

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
                    metadata_saved = False
                    needs_aladin_category_repair = (
                        (book.metadata_source or '').lower() == 'aladin' and
                        ',' in (book.source_category or '')
                    )

                    for f in book.files:
                        if not force_all and f.cover_url and f.author and book.category and \
                                book.category != CATEGORY_UNCLASSIFIED and book.source_category and \
                                not needs_aladin_category_repair:
                            continue

                        meta = enrich_book_info(book.title, volume=f.volume_number, author_hint=known_author)
                        if meta:
                            if (force_all or not known_author) and meta.get('author') not in (None, '알 수 없음', 'Unknown'):
                                known_author = meta['author']
                            if (force_all or not first_cover) and meta.get('cover_url'):
                                first_cover = meta['cover_url']
                            if not metadata_saved:
                                if force_all or not book.isbn_13:
                                    book.isbn_13 = meta.get('isbn') or book.isbn_13
                                if force_all or needs_aladin_category_repair or not book.source_category:
                                    book.source_category = meta.get('source_category') or book.source_category
                                if force_all or needs_aladin_category_repair or not book.category or book.category == CATEGORY_UNCLASSIFIED:
                                    book.category = normalize_app_category(
                                        meta.get('category'),
                                        meta.get('source_category'),
                                    ) if meta.get('category') or meta.get('source_category') else (book.category or CATEGORY_UNCLASSIFIED)
                                if force_all or not book.metadata_source:
                                    book.metadata_source = meta.get('source') or book.metadata_source
                                metadata_saved = True

                            if force_all or not f.title:
                                f.title = meta.get('title') or f.title
                            if force_all or not f.author or f.author in ('알 수 없음', 'Unknown'):
                                f.author = meta.get('author') or f.author
                            if (force_all or not f.cover_url) and meta.get('cover_url'):
                                f.cover_url = meta['cover_url']

                            updated_files_count += 1
                            with cls._lock:
                                cls._status["updated_files"] = updated_files_count

                        time.sleep(0.1) # Courteous rate limit

                    if not book.category:
                        # Keep unmatched books selectable in the shelf instead of silently omitting them.
                        book.category = CATEGORY_UNCLASSIFIED

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
