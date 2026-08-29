import os
import logging
from pathlib import Path
from flask import Blueprint, render_template, request, g, jsonify, url_for, send_from_directory, current_app, abort
from pypdf import PdfReader
from models import db, File, ReadingState
from blueprints.auth import login_required
from services.book_service import resolve_pdf_path

logger = logging.getLogger(__name__)
reader_bp = Blueprint('reader', __name__)

@reader_bp.route('/reader/<int:file_id>')
@login_required
def reader_view(file_id):
    file = File.query.get_or_404(file_id)
    pdf_root = current_app.config.get('PDF_ROOT_PATH')

    resolved_path = resolve_pdf_path(pdf_root, file.file_path)
    if not resolved_path or not resolved_path.exists():
        logger.error(f"PDF file not found on disk: {file.file_path} (Resolved: {resolved_path})")
        abort(404, description="PDF 파일을 찾을 수 없습니다.")

    # Calculate total_pages on first read if still 0
    if file.total_pages == 0:
        try:
            logger.info(f"First read for file_id {file.id}. Calculating total pages from {resolved_path}")
            with PdfReader(str(resolved_path)) as pdf_reader:
                file.total_pages = len(pdf_reader.pages)
            db.session.commit()
            logger.info(f"Updated total_pages for file_id {file.id} to {file.total_pages}")
        except Exception as e:
            db.session.rollback()
            logger.warning(f"Failed to extract page count for {resolved_path}: {e}")

    # Generate relative URL for static_pdfs
    try:
        rel_posix = resolved_path.relative_to(Path(pdf_root).resolve()).as_posix()
    except ValueError:
        # Fallback to file name if outside root
        rel_posix = resolved_path.name

    pdf_url = url_for('reader.static_pdfs', filename=rel_posix)

    # Get or create user reading state (guaranteed unique per user & file)
    state = ReadingState.query.filter_by(user_id=g.user.id, file_id=file.id).first()
    if not state:
        state = ReadingState(user_id=g.user.id, file_id=file.id, current_page=1)
        db.session.add(state)
    db.session.commit()

    return render_template('reader.html', file=file, state=state, pdf_url=pdf_url)

@reader_bp.route('/pdfs/<path:filename>')
@login_required
def static_pdfs(filename):
    """Securely serve PDF files with login protection and HTTP Range support."""
    pdf_root = current_app.config.get('PDF_ROOT_PATH')
    if not pdf_root or not os.path.exists(pdf_root):
        abort(500, description="PDF_ROOT_PATH is not configured properly.")
    return send_from_directory(pdf_root, filename)

@reader_bp.route('/api/status/update', methods=['POST'])
@login_required
def update_status():
    data = request.json or {}
    file_id = data.get('file_id')
    current_page = data.get('current_page')

    if not file_id or current_page is None:
        return jsonify({'error': 'Missing file_id or current_page'}), 400

    try:
        current_page = int(current_page)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid page number'}), 400

    state = ReadingState.query.filter_by(user_id=g.user.id, file_id=file_id).first()
    if not state:
        state = ReadingState(user_id=g.user.id, file_id=file_id, current_page=current_page)
        db.session.add(state)
    else:
        state.current_page = current_page

    db.session.commit()
    return jsonify({'success': True, 'last_read_at': state.last_read_at.isoformat() if state.last_read_at else None})

@reader_bp.route('/api/next_volume/<int:file_id>', methods=['GET'])
@login_required
def get_next_volume(file_id):
    current_file = File.query.get_or_404(file_id)
    next_volume = File.query.filter(
        File.book_id == current_file.book_id,
        File.volume_number == current_file.volume_number + 1
    ).first()

    if next_volume:
        return jsonify({'next_file_id': next_volume.id})
    return jsonify({'next_file_id': None}), 200

@reader_bp.route('/api/file/update', methods=['POST'])
@login_required
def update_file_info():
    data = request.json or {}
    file_id = data.get('file_id')
    file_obj = File.query.get_or_404(file_id)

    if 'title' in data and data['title']:
        file_obj.title = data['title']
    if 'author' in data and data['author']:
        file_obj.author = data['author']
    if 'cover_url' in data and data['cover_url']:
        file_obj.cover_url = data['cover_url']

    db.session.commit()
    return jsonify({
        "success": True,
        "file": {
            "id": file_obj.id,
            "title": file_obj.title,
            "author": file_obj.author,
            "cover_url": file_obj.cover_url
        }
    })
