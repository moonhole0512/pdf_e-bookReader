from flask import Blueprint, render_template, request, g, jsonify
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

    # 1. 가장 최근 읽은 책 (1권)
    last_read_state = ReadingState.query.filter_by(user_id=user_id)\
        .order_by(ReadingState.last_read_at.desc())\
        .first()

    # 2. 독서 중인 책 목록 (최근 읽은 순 상위 5개 그룹)
    reading_book_ids_query = db.session.query(File.book_id)\
        .join(ReadingState, ReadingState.file_id == File.id)\
        .filter(ReadingState.user_id == user_id)\
        .order_by(ReadingState.last_read_at.desc())\
        .distinct()

    if last_read_state and last_read_state.file:
        reading_book_ids_query = reading_book_ids_query.filter(File.book_id != last_read_state.file.book_id)

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

    last_file = last_read_state.file if last_read_state else None
    next_volume_file = None
    if last_file:
        next_volume_file = File.query.filter_by(
            book_id=last_file.book_id,
            volume_number=last_file.volume_number + 1
        ).first()

    return render_template(
        'index.html',
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
