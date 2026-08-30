from flask import Blueprint, render_template, request, g, jsonify, redirect, url_for
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from models import db, Book, File, ReadingState
from blueprints.auth import login_required
from services.book_service import group_files_by_book, get_recommended_books

library_bp = Blueprint('library', __name__)

@library_bp.route('/')
@login_required
def index():
    user_id = g.user.id

    # 1. 가장 최근 읽은 책들 (최대 3권)
    recent_states = ReadingState.query.filter_by(user_id=user_id)\
        .join(File, ReadingState.file_id == File.id)\
        .options(joinedload(ReadingState.file).joinedload(File.book))\
        .order_by(ReadingState.last_read_at.desc())\
        .all()

    recent_lounge_items = []
    seen_book_ids = set()
    for state in recent_states:
        if not state.file or not state.file.book:
            continue
        book_id = state.file.book_id
        if book_id in seen_book_ids:
            continue
        seen_book_ids.add(book_id)

        f = state.file
        pct = round((state.current_page / f.total_pages) * 100) if f.total_pages > 0 else 0
        pages_left = (f.total_pages - state.current_page) if f.total_pages > 0 else 0

        next_vol = File.query.filter_by(
            book_id=f.book_id,
            volume_number=f.volume_number + 1
        ).first()

        recent_lounge_items.append({
            'file': f,
            'state': state,
            'pct': pct,
            'pages_left': pages_left,
            'next_volume_file': next_vol
        })
        if len(recent_lounge_items) >= 4:
            break

    # 2. 독서 중인 책 목록 (상단 라운지에 노출되지 않은 나머지 독서 중 그룹 상위 5개)
    reading_book_ids_query = db.session.query(File.book_id)\
        .join(ReadingState, ReadingState.file_id == File.id)\
        .filter(ReadingState.user_id == user_id)\
        .order_by(ReadingState.last_read_at.desc())\
        .distinct()

    if seen_book_ids:
        reading_book_ids_query = reading_book_ids_query.filter(File.book_id.notin_(seen_book_ids))

    reading_book_ids = [item[0] for item in reading_book_ids_query.limit(5).all()]
    reading_groups = []
    if reading_book_ids:
        reading_files = File.query.options(joinedload(File.book))\
            .filter(File.book_id.in_(reading_book_ids)).all()
        reading_groups = group_files_by_book(reading_files, user_id)

    # 3. 추천 책 목록 (메모리 낭비 없이 RANDOM LIMIT 5)
    recommended_books = get_recommended_books(limit=5)
    recommended_groups = []
    if recommended_books:
        rec_ids = [b.id for b in recommended_books]
        rec_files = File.query.options(joinedload(File.book))\
            .filter(File.book_id.in_(rec_ids)).all()
        recommended_groups = group_files_by_book(rec_files, user_id)

    # 4. 모든 책 목록 (검색 및 페이징)
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search_query', '').strip()

    all_books_query = Book.query.order_by(Book.title)
    if search_query:
        all_books_query = all_books_query.filter(Book.title.ilike(f'%{search_query}%'))

    pagination = all_books_query.paginate(page=page, per_page=10, error_out=False)
    paginated_book_ids = [b.id for b in pagination.items]

    all_groups = []
    if paginated_book_ids:
        all_files = File.query.options(joinedload(File.book))\
            .filter(File.book_id.in_(paginated_book_ids)).all()
        all_groups = group_files_by_book(all_files, user_id)

    total_books = pagination.total
    total_files = db.session.query(func.count(File.id)).scalar() or 0

    last_file = recent_lounge_items[0]['file'] if recent_lounge_items else None
    next_volume_file = recent_lounge_items[0]['next_volume_file'] if recent_lounge_items else None

    return render_template(
        'index.html',
        recent_lounge_items=recent_lounge_items,
        last_read_file=last_file,
        next_volume_file=next_volume_file,
        reading_groups=reading_groups,
        recommended_groups=recommended_groups,
        all_groups=all_groups,
        pagination=pagination,
        search_query=search_query,
        total_books=total_books,
        total_files=total_files
    )

@library_bp.route('/api/books')
@login_required
def get_books():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search_query', '').strip()

    # Guard: If user visits /api/books directly in browser address bar, redirect to the full index view
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
              request.headers.get('Sec-Fetch-Dest') == 'empty' or \
              'text/html' not in request.headers.get('Accept', '')
    if not is_ajax and request.headers.get('Sec-Fetch-Dest') == 'document':
        return redirect(url_for('library.index', page=page, search_query=search_query))

    all_books_query = Book.query.order_by(Book.title)
    if search_query:
        all_books_query = all_books_query.filter(Book.title.ilike(f'%{search_query}%'))

    pagination = all_books_query.paginate(page=page, per_page=10, error_out=False)
    paginated_book_ids = [item.id for item in pagination.items]

    all_groups = []
    if paginated_book_ids:
        all_files = File.query.options(joinedload(File.book))\
            .filter(File.book_id.in_(paginated_book_ids)).all()
        all_groups = group_files_by_book(all_files, g.user.id)

    return render_template('_book_list.html', all_groups=all_groups, pagination=pagination, search_query=search_query)

@library_bp.route('/api/books/autocomplete')
def autocomplete_books():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    books = db.session.query(Book.title)\
        .filter(Book.title.ilike(f'%{query}%'))\
        .distinct()\
        .limit(10)\
        .all()
    titles = [book[0] for book in books]
    return jsonify(titles)
