import logging
from flask import Blueprint, request, jsonify, current_app
from models import db, Book
from blueprints.auth import login_required
from services.scanner import LibraryScanner

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/scan', methods=['GET', 'POST'])
@login_required
def trigger_scan():
    """
    Triggers non-blocking background scan.
    Accepts batch_size and optional clean_missing parameters.
    """
    if request.is_json:
        data = request.json or {}
        batch_size = data.get('batch_size', 30)
        clean_missing = data.get('clean_missing', False)
    else:
        batch_size = request.args.get('batch_size', default=30, type=int)
        clean_missing = request.args.get('clean_missing', default='false').lower() in ('true', '1')

    if batch_size <= 0:
        batch_size = 30

    app = current_app._get_current_object()
    started = LibraryScanner.start_scan(app, batch_size=batch_size, clean_missing=clean_missing)

    if started:
        return jsonify({
            "success": True,
            "message": "백그라운드에서 PDF 스캔을 시작했습니다.",
            "status": LibraryScanner.get_status()
        })
    else:
        return jsonify({
            "success": False,
            "message": "이미 PDF 스캔 작업이 진행 중입니다.",
            "status": LibraryScanner.get_status()
        }), 409

@admin_bp.route('/api/admin/scan/status', methods=['GET'])
@login_required
def scan_status():
    """Returns current status of the background scanner for client polling."""
    return jsonify(LibraryScanner.get_status())

@admin_bp.route('/admin/metadata/update', methods=['POST'])
@login_required
def update_metadata():
    data = request.json or {}
    book_id = data.get('book_id')
    title = data.get('title')
    author = data.get('author')

    if not book_id:
        return jsonify({"error": "book_id is required"}), 400

    book = Book.query.get_or_404(book_id)
    if title:
        book.title = title.strip()
    if author:
        book.author = author.strip()
    
    db.session.commit()
    logger.info(f"Updated metadata for Book {book_id}: title='{book.title}', author='{book.author}'")

    return jsonify({"success": True, "message": "도서 정보가 성공적으로 업데이트되었습니다."})

@admin_bp.route('/api/admin/enrich', methods=['POST'])
@login_required
def trigger_enrichment():
    """Triggers background metadata enrichment for the library."""
    from services.book_enricher import LibraryEnricher
    data = request.json or {}
    force_all = data.get('force_all', False)

    app = current_app._get_current_object()
    started = LibraryEnricher.start_enrichment(app, force_all=force_all)

    if started:
        return jsonify({
            "success": True,
            "message": "도서 정보 자동 검색 및 표지 다운로드를 시작했습니다.",
            "status": LibraryEnricher.get_status()
        })
    else:
        return jsonify({
            "success": False,
            "message": "이미 도서 정보 검색 작업이 진행 중입니다.",
            "status": LibraryEnricher.get_status()
        }), 409

@admin_bp.route('/api/admin/enrich/status', methods=['GET'])
@login_required
def enrichment_status():
    """Returns current status of the background library enricher."""
    from services.book_enricher import LibraryEnricher
    return jsonify(LibraryEnricher.get_status())
