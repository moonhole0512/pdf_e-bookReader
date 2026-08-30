import logging
from flask import Blueprint, request, jsonify
from services.books_api import lookup_google_books_by_title_volume, lookup_google_books_by_isbn
from blueprints.auth import login_required

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

@api_bp.route('/api/book/lookup_by_title_volume')
@login_required
def book_lookup_by_title_volume():
    title = request.args.get('title')
    volume = request.args.get('volume')

    if not title:
        return jsonify({"error": "Title is required"}), 400

    vol_num = int(float(volume)) if volume and volume.replace('.', '', 1).isdigit() else None

    # Multi-source candidate search (Aladin + Google Books)
    try:
        from services.book_enricher import search_book_candidates
        candidates = search_book_candidates(title, volume=vol_num)
        if candidates:
            if len(candidates) == 1:
                return jsonify(candidates[0])
            return jsonify(candidates)
    except Exception as e:
        logger.debug(f"Candidate search error: {e}")

    # Fallback to Google Books API
    resp = lookup_google_books_by_title_volume(title, volume)
    if resp.get("status") != 200:
        return jsonify({"error": resp.get("error", "Error")}), resp.get("status", 500)

    results = resp.get("results", [])
    if not results:
        return jsonify({"error": "도서 정보를 찾을 수 없습니다."}), 404

    if len(results) == 1:
        return jsonify(results[0])
    return jsonify(results)

@api_bp.route('/api/book/lookup')
@login_required
def book_lookup():
    isbn = request.args.get('isbn')
    if not isbn:
        return jsonify({"error": "ISBN is required"}), 400

    # 1. Try Aladin by ISBN first (Accurate Korean light novel / fiction data, 500px covers, no 429 quota)
    try:
        from services.book_enricher import search_book_candidates
        cands = search_book_candidates(isbn)
        if cands:
            c = cands[0]
            return jsonify({
                "title": c.get('title'),
                "author": c.get('author'),
                "thumbnail": c.get('thumbnail'),
                "isbn_13": c.get('isbn_13'),
                "isbn_10": c.get('isbn_10'),
                "alt_images": []
            })
    except Exception as e:
        logger.debug(f"Aladin ISBN lookup failed: {e}")

    # 2. Fallback to Google Books
    resp = lookup_google_books_by_isbn(isbn)
    if resp.get("status") == 200 and resp.get("result"):
        return jsonify(resp.get("result"))

    return jsonify({"error": "도서 정보를 찾을 수 없습니다."}), 404
