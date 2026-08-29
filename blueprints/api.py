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

    # 1. Try high-precision Aladin enrichment first
    try:
        from services.book_enricher import enrich_book_info
        vol_num = int(float(volume)) if volume and volume.replace('.', '', 1).isdigit() else 1
        enriched = enrich_book_info(title, volume=vol_num)
        if enriched and enriched.get('cover_url'):
            return jsonify({
                "title": enriched['title'],
                "author": enriched['author'],
                "thumbnail": enriched.get('cover_url'),
                "isbn_13": enriched.get('isbn'),
                "isbn_10": None
            })
    except Exception as e:
        logger.debug(f"Aladin enrichment check error: {e}")

    # 2. Fallback to Google Books API
    resp = lookup_google_books_by_title_volume(title, volume)
    if resp.get("status") != 200:
        return jsonify({"error": resp.get("error", "Error")}), resp.get("status", 500)

    results = resp.get("results", [])
    if not results:
        return jsonify({"error": "No book found for the given title and volume."}), 404

    # Keep exact legacy response contract for library.js
    if len(results) == 1:
        return jsonify(results[0])
    return jsonify(results)

@api_bp.route('/api/book/lookup')
@login_required
def book_lookup():
    isbn = request.args.get('isbn')
    if not isbn:
        return jsonify({"error": "ISBN is required"}), 400

    resp = lookup_google_books_by_isbn(isbn)
    if resp.get("status") != 200:
        return jsonify({"error": resp.get("error", "Error")}), resp.get("status", 500)

    return jsonify(resp.get("result"))
