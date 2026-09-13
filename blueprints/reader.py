import os
import time
import logging
from pathlib import Path
from flask import Blueprint, render_template, request, g, jsonify, url_for, send_from_directory, send_file, current_app, abort
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from models import db, File, ReadingState, PageEdit
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
        return jsonify({
            'next_file_id': next_volume.id,
            'next_volume_number': next_volume.volume_number,
            'next_title': next_volume.title or (next_volume.book.title if next_volume.book else "")
        })
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

    # Synchronize parent Book record (cover, author, clean title)
    if file_obj.book:
        if file_obj.volume_number == 1 or not file_obj.book.cover_url:
            if 'cover_url' in data and data['cover_url']:
                file_obj.book.cover_url = data['cover_url']
        if not file_obj.book.author or file_obj.book.author in ("Unknown", "알 수 없음"):
            if 'author' in data and data['author']:
                file_obj.book.author = data['author']
        if file_obj.volume_number == 1 and 'title' in data and data['title']:
            from services.book_enricher import clean_book_title
            file_obj.book.title = clean_book_title(data['title'])
        for field in ('isbn_13', 'source_category', 'category', 'metadata_source'):
            if data.get(field):
                setattr(file_obj.book, field, data[field])

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

# --- Hybrid Page Management APIs (Zero-Server-Load Staging & Commit) ---

@reader_bp.route('/api/page/edits/<int:file_id>', methods=['GET'])
@login_required
def get_page_edits(file_id):
    """Retrieve all pending virtual edits for a given file."""
    edits = PageEdit.query.filter_by(file_id=file_id).order_by(PageEdit.page_num.asc(), PageEdit.id.asc()).all()
    return jsonify({
        "success": True,
        "edits": [e.to_dict() for e in edits]
    })

@reader_bp.route('/api/page/pending_edits', methods=['GET'])
@login_required
def get_all_pending_edits():
    """Retrieve all pending edits across the library for the batch commit modal."""
    edits = PageEdit.query.order_by(PageEdit.file_id.asc(), PageEdit.page_num.asc()).all()
    return jsonify({
        "success": True,
        "total_count": len(edits),
        "edits": [e.to_dict() for e in edits]
    })

@reader_bp.route('/api/page/edit', methods=['POST'])
@login_required
def create_page_edit():
    """
    Stage a virtual page edit: replace, delete, or insert.
    Saves only lightweight metadata and single image if applicable (Zero NAS RAM overhead).
    """
    file_id = request.form.get('file_id', type=int)
    page_num = request.form.get('page_num', type=int)
    action = request.form.get('action') # 'replace', 'delete', 'insert_before', 'insert_after'

    if not file_id or not page_num or action not in ('replace', 'delete', 'insert_before', 'insert_after'):
        return jsonify({"success": False, "message": "유효하지 않은 요청 매개변수입니다."}), 400

    file_obj = File.query.get_or_404(file_id)
    image_rel_path = None

    if action in ('replace', 'insert_before', 'insert_after'):
        if 'image' not in request.files or not request.files['image'].filename:
            return jsonify({"success": False, "message": "교체할 이미지를 업로드해야 합니다."}), 400
        
        img_file = request.files['image']
        ext = os.path.splitext(secure_filename(img_file.filename))[1].lower() or '.jpg'
        
        edits_dir = os.path.join(current_app.instance_path, 'edits', str(file_id))
        os.makedirs(edits_dir, exist_ok=True)
        
        img_filename = f"p{page_num}_{int(time.time()*1000)}{ext}"
        img_full_path = os.path.join(edits_dir, img_filename)
        img_file.save(img_full_path)
        image_rel_path = os.path.join('edits', str(file_id), img_filename).replace('\\', '/')

    # If replacing a page that already has a replace edit, overwrite the existing edit
    if action == 'replace':
        existing = PageEdit.query.filter_by(file_id=file_id, page_num=page_num, action='replace').first()
        if existing:
            if existing.image_path:
                old_path = os.path.join(current_app.instance_path, existing.image_path)
                if os.path.exists(old_path):
                    try: os.remove(old_path)
                    except Exception: pass
            existing.image_path = image_rel_path
            db.session.commit()
            return jsonify({"success": True, "edit": existing.to_dict()})

    # If deleting a page that was marked delete, avoid duplicates
    if action == 'delete':
        existing = PageEdit.query.filter_by(file_id=file_id, page_num=page_num, action='delete').first()
        if existing:
            return jsonify({"success": True, "edit": existing.to_dict()})

    edit = PageEdit(
        file_id=file_id,
        page_num=page_num,
        action=action,
        image_path=image_rel_path
    )
    db.session.add(edit)
    db.session.commit()

    return jsonify({"success": True, "edit": edit.to_dict()})

@reader_bp.route('/api/page/edit/<int:edit_id>/cancel', methods=['POST'])
@login_required
def cancel_page_edit(edit_id):
    """Cancel and rollback a pending page edit."""
    edit = PageEdit.query.get_or_404(edit_id)
    if edit.image_path:
        img_path = os.path.join(current_app.instance_path, edit.image_path)
        if os.path.exists(img_path):
            try: os.remove(img_path)
            except Exception: pass
    
    file_id = edit.file_id
    db.session.delete(edit)
    db.session.commit()
    return jsonify({"success": True, "file_id": file_id})

@reader_bp.route('/api/page/override_image/<int:edit_id>', methods=['GET'])
@login_required
def get_override_image(edit_id):
    """Serve the override image for a staged page edit."""
    edit = PageEdit.query.get_or_404(edit_id)
    if not edit.image_path:
        abort(404)
    full_path = os.path.join(current_app.instance_path, edit.image_path)
    if not os.path.exists(full_path):
        abort(404)
    return send_file(full_path)

@reader_bp.route('/api/file/replace_pdf', methods=['POST'])
@login_required
def replace_pdf_file():
    """
    Commit step: Client browser (pdf-lib) has assembled the final merged PDF.
    Server simply writes the binary stream to disk, updates total_pages, and purges edits.
    Zero memory/CPU parsing overhead for the NAS.
    """
    file_id = request.form.get('file_id', type=int)
    if not file_id or 'pdf' not in request.files:
        return jsonify({"success": False, "message": "유효하지 않은 요청입니다."}), 400

    file_obj = File.query.get_or_404(file_id)
    pdf_root = current_app.config.get('PDF_ROOT_PATH')
    resolved_path = resolve_pdf_path(pdf_root, file_obj.file_path)

    if not resolved_path:
        return jsonify({"success": False, "message": "파일 경로를 확인할 수 없습니다."}), 404

    uploaded_pdf = request.files['pdf']
    temp_target = str(resolved_path) + ".tmp"
    uploaded_pdf.save(temp_target)
    os.replace(temp_target, str(resolved_path))

    try:
        with PdfReader(str(resolved_path)) as reader:
            file_obj.total_pages = len(reader.pages)
    except Exception as e:
        logger.warning(f"Failed to read updated page count: {e}")

    edits = PageEdit.query.filter_by(file_id=file_id).all()
    for e in edits:
        if e.image_path:
            p = os.path.join(current_app.instance_path, e.image_path)
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass
        db.session.delete(e)

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "PDF가 성공적으로 영구 갱신되었습니다!",
        "file_id": file_obj.id,
        "total_pages": file_obj.total_pages
    })
