
import os
import re
from pathlib import Path
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, g, send_from_directory
from sqlalchemy import func, desc, text
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
from pypdf import PdfReader
import requests
import time
import random
import logging

from config import Config
from models import db, User, Book, File, ReadingState

# Gunicorn과 같은 운영 서버는 자체 로깅 설정을 사용합니다.
# 로컬 개발 환경(Waitress) 또는 직접 실행 시에만 기본 로깅을 설정하여
# Gunicorn 환경에 영향을 주지 않고 콘솔 로그를 활성화합니다.
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s in %(module)s: %(message)s')


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

# Log DNS server info for debugging
resolv_conf_path = '/etc/resolv.conf'
if os.path.exists(resolv_conf_path):
    try:
        with open(resolv_conf_path, 'r') as f:
            dns_info = f.read()
            app.logger.info(f"DNS config at {resolv_conf_path}:\n---\n{dns_info}---")
    except Exception as e:
        app.logger.error(f"Could not read {resolv_conf_path}: {e}")
else:
    app.logger.info(f"DNS config file not found at {resolv_conf_path} (This is normal on non-Linux systems).")


def unlock_database():
    """DB 락을 해제합니다."""
    with app.app_context():
        try:
            # 간단한 쿼리를 실행하여 연결을 확인하고 복구를 트리거합니다.
            db.session.execute(text('SELECT 1'))
            db.session.commit()
        except OperationalError as e:
            if "database is locked" in str(e).lower():
                app.logger.warning("데이터베이스가 잠겨 있었습니다. 빈 트랜잭션을 커밋하여 잠금 해제를 시도합니다.")
                # 롤백 후 커밋하여 잠금을 해제합니다.
                db.session.rollback()
                db.session.commit()
                app.logger.info("데이터베이스 잠금이 해제되었습니다.")
            else:
                # 다른 OperationalError는 다시 발생시킵니다.
                raise

def init_db():
    with app.app_context():
        # 설정에서 절대 DB 경로를 가져옵니다.
        db_path = app.config['DB_PATH']
        # 해당 경로의 디렉터리를 확인하고 생성합니다.
        db_dir = os.path.dirname(db_path)
        os.makedirs(db_dir, exist_ok=True)

        app.logger.info(f"Database path: {db_path}")
        db.create_all()
        app.logger.info("Database initialized.")

# 데이터베이스 테이블이 존재하지 않으면 생성합니다.
# Gunicorn, Waitress 등 어떤 WSGI 서버를 사용하든 앱 임포트 시 실행되도록 합니다.
with app.app_context():
    init_db()
    unlock_database()

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = db.session.get(User, user_id) if user_id is not None else None

def group_files_by_book(files, user_id):
    groups = {}
    file_ids = [f.id for f in files]
    
    # Fetch all relevant reading states in one query
    reading_states = db.session.query(ReadingState).filter(
        ReadingState.user_id == user_id,
        ReadingState.file_id.in_(file_ids)
    ).all()
    states_by_file_id = {state.file_id: state for state in reading_states}

    for file in files:
        if file.book_id not in groups:
            groups[file.book_id] = []
        groups[file.book_id].append(file)
    
    grouped_list = []
    for book_id, file_list in groups.items():
        file_list.sort(key=lambda f: f.volume_number)
        cover_file = next((f for f in file_list if f.volume_number == 1), file_list[0])
        
        serializable_files = []
        for f in file_list:
            reading_state = states_by_file_id.get(f.id)
            current_page = reading_state.current_page if reading_state else 0

            serializable_files.append({
                "id": f.id, 
                "title": f.title or f.book.title, 
                "author": f.author or f.book.author, 
                "volume_number": f.volume_number, 
                "cover_url": f.cover_url or f.book.cover_url,
                "current_page": current_page,
                "total_pages": f.total_pages
            })

        grouped_list.append({
            "book": file_list[0].book,
            "files": serializable_files,
            "volume_count": len(file_list),
            "cover_file": cover_file
        })
    
    grouped_list.sort(key=lambda g: g['book'].title)
    return grouped_list

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        user = User.query.filter_by(username=username).first()
        if not user:
            app.logger.info(f"New user '{username}' created.")
            user = User(username=username, password_hash=None) # No password needed
            db.session.add(user)
            db.session.commit()
        
        session.clear()
        session['user_id'] = user.id
        return redirect(url_for('index'))
    
    users = User.query.all()
    return render_template('login.html', users=users)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not g.user:
        return redirect(url_for('login'))

    # 1. 가장 최근 읽은 책 (1권) - 유지
    last_read_state = ReadingState.query.filter_by(user_id=g.user.id).order_by(desc(ReadingState.last_read_at)).first()
    
    # 2. 독서 중인 책 목록 (그룹화)
    reading_book_ids_query = db.session.query(File.book_id).join(ReadingState).filter(ReadingState.user_id == g.user.id).order_by(desc(ReadingState.last_read_at)).distinct()
    if last_read_state:
        reading_book_ids_query = reading_book_ids_query.filter(File.book_id != last_read_state.file.book_id)
    
    reading_book_ids = [item[0] for item in reading_book_ids_query.limit(5).all()]

    reading_groups = []
    if reading_book_ids:
        reading_files_query = File.query.filter(File.book_id.in_(reading_book_ids)).all()
        reading_groups = group_files_by_book(reading_files_query, g.user.id)

    # 3. 추천 책 목록 (랜덤 5개 그룹화)
    all_book_ids_query = db.session.query(Book.id).all()
    all_book_ids = [book.id for book in all_book_ids_query]
    if len(all_book_ids) > 5:
        random_book_ids = random.sample(all_book_ids, 5)
    else:
        random_book_ids = all_book_ids

    recommended_files_query = File.query.filter(File.book_id.in_(random_book_ids)).all()
    recommended_groups = group_files_by_book(recommended_files_query, g.user.id)

    # 4. 모든 책 목록 (그룹화)
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search_query', '')
    
    all_books_query = Book.query.order_by(Book.title)
    if search_query:
        all_books_query = all_books_query.filter(Book.title.ilike(f'%{search_query}%'))

    pagination = all_books_query.paginate(page=page, per_page=10, error_out=False)
    paginated_book_ids = [item.id for item in pagination.items]

    all_groups = []
    if paginated_book_ids:
        all_files_query = File.query.filter(File.book_id.in_(paginated_book_ids)).all()
        all_groups = group_files_by_book(all_files_query, g.user.id)

    total_books = pagination.total
    total_files = db.session.query(func.count(File.id)).scalar()

    return render_template('index.html', 
                           last_read_file=last_read_state.file if last_read_state else None,
                           reading_groups=reading_groups,
                           recommended_groups=recommended_groups,
                           all_groups=all_groups,
                           pagination=pagination,
                           search_query=search_query,
                           total_books=total_books,
                           total_files=total_files)

@app.route('/reader/<int:file_id>')
def reader(file_id):
    if not g.user:
        return redirect(url_for('login'))
        
    file = File.query.get_or_404(file_id)

    # If total_pages is 0, calculate it now and update the DB.
    if file.total_pages == 0:
        try:
            app.logger.info(f"First read for file_id {file.id}. Calculating total pages.")
            with PdfReader(file.file_path) as pdf_reader:
                file.total_pages = len(pdf_reader.pages)
            db.session.commit()
            app.logger.info(f"Updated total_pages for file_id {file.id} to {file.total_pages}.")
        except Exception as e:
            app.logger.error(f"Failed to read PDF and update page count for {file.file_path}: {e}")
            # Rollback in case of error during page count update
            db.session.rollback()

    # Ensure the file path is safe and relative to the root
    pdf_path = Path(file.file_path)
    root_path = Path(app.config['PDF_ROOT_PATH'])
    if not pdf_path.is_relative_to(root_path):
        return "Invalid file path", 400

    # Create a relative path for the URL
    relative_path = pdf_path.relative_to(root_path).as_posix()
    pdf_url = url_for('static_pdfs', filename=relative_path)

    # Update reading state
    state = ReadingState.query.filter_by(user_id=g.user.id, file_id=file.id).first()
    if not state:
        state = ReadingState(user_id=g.user.id, file_id=file.id, current_page=1)
        db.session.add(state)
    db.session.commit() # last_read_at is updated automatically

    return render_template('reader.html', file=file, state=state, pdf_url=pdf_url)

@app.route('/pdfs/<path:filename>')
def static_pdfs(filename):
    return send_from_directory(app.config['PDF_ROOT_PATH'], filename)

# --- API Endpoints ---

@app.route('/api/status/update', methods=['POST'])
def update_status():
    if not g.user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    file_id = data.get('file_id')
    current_page = data.get('current_page')

    if not file_id or not current_page:
        return jsonify({'error': 'Missing data'}), 400

    state = ReadingState.query.filter_by(user_id=g.user.id, file_id=file_id).first()
    if state:
        app.logger.info(f"User '{g.user.username}' updated reading status for file_id {file_id} to page {current_page}.")
        state.current_page = int(current_page)
        db.session.commit()
        return jsonify({'success': True, 'last_read_at': state.last_read_at.isoformat()})
    
    return jsonify({'error': 'Reading state not found'}), 404

@app.route('/api/next_volume/<int:file_id>', methods=['GET'])
def get_next_volume(file_id):
    current_file = File.query.get_or_404(file_id)
    next_volume = File.query.filter(
        File.book_id == current_file.book_id,
        File.volume_number == current_file.volume_number + 1
    ).first()

    if next_volume:
        return jsonify({'next_file_id': next_volume.id})
    else:
        return jsonify({'next_file_id': None}), 200 # Return 200 OK with None if no next volume

@app.route('/admin/scan', methods=['GET']) # Should be POST in production with auth
def scan_files():
    app.logger.info("Starting PDF scan...")
    batch_size = request.args.get('batch_size', default=30, type=int)
    if batch_size <= 0:
        app.logger.warning(f"Invalid batch_size '{batch_size}' received. Falling back to default 30.")
        batch_size = 30 # 0 또는 음수 값일 경우 기본값으로 복귀

    pdf_root = app.config['PDF_ROOT_PATH']
    if not pdf_root or not os.path.exists(pdf_root):
        app.logger.error("PDF_ROOT_PATH is not configured or does not exist.")
        return jsonify({"error": "PDF_ROOT_PATH is not configured or does not exist."}), 500

    added_files_count = 0
    processed_count = 0
    # Optimize by fetching only file_path strings, not full objects
    existing_files = {row[0] for row in db.session.query(File.file_path).all()}
    
    app.logger.info("Starting to scan for new PDF files...")

    # Process files one by one instead of loading all paths into memory
    for pdf_path in Path(pdf_root).rglob('*.pdf'):
        pdf_path_str = str(pdf_path)
        if pdf_path_str in existing_files:
            continue

        processed_count += 1 # Count only new files being processed
        app.logger.info(f"Processing new file {processed_count}: {pdf_path_str}")
        try:
            # Extract metadata from filename
            filename = Path(pdf_path_str).stem
            
            # Regex to handle cases like: "Title_01", "Title_01.5", "Title_01_special", "Title 1", "Title01"
            match = re.match(r'^(.*?)(?:[\s_-]*)(\d+(?:\.\d+)?)(?:_.*)?$', filename)
            
            if match:
                title, volume_str = match.groups()
                title = title.strip()
                if not title or title.isdigit():
                    title = filename
                    volume = 1
                else:
                    # For volumes like "1.5", store the integer part for sorting,
                    # but the full filename is stored in File.title for display.
                    volume = int(float(volume_str))
            else:
                title = filename
                volume = 1
            
            title = title.strip()

            # Get or create book
            book = Book.query.filter_by(title=title).first()
            if not book:
                app.logger.info(f"New book found: '{title}'. Creating new entry.")
                book = Book(title=title, author="Unknown")
                db.session.add(book)
                db.session.flush() # To get book.id

            # Create file entry with total_pages=0. It will be updated on first read.
            # The original filename is stored in the file's title field.
            new_file = File(
                book_id=book.id,
                file_path=pdf_path_str,
                volume_number=volume,
                total_pages=0, # Set default to 0
                title=filename, # Use original filename for file-specific title
                author=book.author
            )
            db.session.add(new_file)
            added_files_count += 1

            # Commit in batches
            if added_files_count % batch_size == 0:
                app.logger.info(f"Committing batch of {batch_size} files to database.")
                db.session.commit()
                time.sleep(0.5) # Add a delay to reduce I/O load after commit

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Failed to process {pdf_path_str}: {e}")

    # Commit any remaining files
    if added_files_count % batch_size != 0:
        app.logger.info(f"Committing remaining {added_files_count % batch_size} files.")
        db.session.commit()

    # Update total_volumes for all books after all files are added
    # This is less efficient but safer than trying to update volumes mid-transaction
    try:
        app.logger.info("Updating total volume counts for all books.")
        all_books = Book.query.all()
        for book in all_books:
            count = db.session.query(func.count(File.id)).filter_by(book_id=book.id).scalar()
            if book.total_volumes != count:
                book.total_volumes = count
        db.session.commit()
        app.logger.info("Total volume counts updated.")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Failed to update total volumes: {e}")


    app.logger.info(f"Scan complete. Added {added_files_count} new files in total.")
    return jsonify({"message": f"스캔 완료. {added_files_count}개의 새 파일을 추가했습니다.", "files_added": added_files_count})

@app.route('/admin/metadata/update', methods=['POST'])
def update_metadata():
    data = request.json
    book_id = data.get('book_id')
    title = data.get('title')
    author = data.get('author')

    book = db.get_or_404(Book, book_id)
    app.logger.info(f"Updating metadata for book_id {book_id}: title='{title}', author='{author}'")
    if title: book.title = title
    if author: book.author = author
    db.session.commit()

    return jsonify({"success": True, "message": "Metadata updated."})

@app.route('/api/book/lookup_by_title_volume')
def lookup_by_title_volume():
    title = request.args.get('title')
    volume = request.args.get('volume')
    app.logger.info(f"Received book lookup request for title: '{title}', volume: '{volume}'")

    if not title:
        app.logger.warning("Title is required but was not provided.")
        return jsonify({"error": "Title is required"}), 400

    processed_title = title.replace(' ', '')
    query_parts = [processed_title]
    if volume:
        query_parts.append(volume)
    
    query = f"\"{' '.join(query_parts)}\""
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&langRestrict=ko"
    app.logger.info(f"Requesting Google Books API with URL: {url}")

    try:
        response = requests.get(url, timeout=10)
        app.logger.info(f"Google Books API response status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        app.logger.debug(f"Google Books API response data: {data}")

        if not data.get('items'):
            app.logger.warning(f"No book found for title: '{title}', volume: '{volume}'")
            return jsonify({"error": "No book found for the given title and volume."}), 404

        results = []
        for item in data['items']:
            volume_info = item['volumeInfo']
            industry_identifiers = volume_info.get('industryIdentifiers', [])
            isbn_13 = next((id['identifier'] for id in industry_identifiers if id['type'] == 'ISBN_13'), None)
            isbn_10 = next((id['identifier'] for id in industry_identifiers if id['type'] == 'ISBN_10'), None)

            results.append({
                "title": volume_info.get('title'),
                "author": ", ".join(volume_info.get('authors', [])),
                "thumbnail": volume_info.get('imageLinks', {}).get('thumbnail'),
                "isbn_13": isbn_13,
                "isbn_10": isbn_10
            })
        
        app.logger.info(f"Found {len(results)} results for title: '{title}', volume: '{volume}'")
        if len(results) == 1:
            return jsonify(results[0])

        return jsonify(results)

    except requests.exceptions.Timeout:
        app.logger.error(f"Google Books API request timed out for URL: {url}")
        return jsonify({"error": "API request timed out"}), 504
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Google Books API request failed for URL: {url}. Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/book/lookup')
def lookup_book():
    isbn = request.args.get('isbn')
    app.logger.info(f"Received ISBN lookup request for ISBN: {isbn}")
    if not isbn:
        app.logger.warning("ISBN is required but was not provided.")
        return jsonify({"error": "ISBN is required"}), 400

    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    app.logger.info(f"Requesting Google Books API with URL: {url}")

    try:
        response = requests.get(url, timeout=10)
        app.logger.info(f"Google Books API response status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        app.logger.debug(f"Google Books API response data: {data}")

        if not data.get('items'):
            app.logger.warning(f"Book not found for ISBN: {isbn}")
            return jsonify({"error": "Book not found"}), 404

        volume_info = data['items'][0]['volumeInfo']
        result = {
            "title": volume_info.get('title'),
            "author": ", ".join(volume_info.get('authors', [])),
            "thumbnail": volume_info.get('imageLinks', {}).get('thumbnail'),
            "alt_images": []
        }
        app.logger.info(f"Successfully found book '{result['title']}' for ISBN: {isbn}")

        if not result['thumbnail']:
            app.logger.info(f"No thumbnail found for ISBN: {isbn}. Alternate image search logic skipped.")
            pass

        return jsonify(result)

    except requests.exceptions.Timeout:
        app.logger.error(f"Google Books API request timed out for ISBN: {isbn}. URL: {url}")
        return jsonify({"error": "API request timed out"}), 504
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Google Books API request failed for ISBN: {isbn}. URL: {url}. Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/file/update', methods=['POST'])
def update_file_info():
    if not g.user:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    file_id = data.get('file_id')
    file_obj = File.query.get_or_404(file_id)

    file_obj.title = data.get('title', file_obj.title)
    file_obj.author = data.get('author', file_obj.author)
    file_obj.cover_url = data.get('cover_url', file_obj.cover_url)
    
    db.session.commit()
    
    return jsonify({"success": True, "file": {
        "id": file_obj.id,
        "title": file_obj.title,
        "author": file_obj.author,
        "cover_url": file_obj.cover_url
    }})

@app.route('/api/books/autocomplete')
def autocomplete_books():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])

    books = db.session.query(Book.title).filter(Book.title.ilike(f'%{query}%')).distinct().limit(10).all()
    titles = [book[0] for book in books]
    return jsonify(titles)

@app.route('/api/books')
def get_books():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search_query', '')
    
    all_books_query = Book.query.order_by(Book.title)
    if search_query:
        all_books_query = all_books_query.filter(Book.title.ilike(f'%{search_query}%'))

    pagination = all_books_query.paginate(page=page, per_page=10, error_out=False)
    all_book_ids = [item.id for item in pagination.items]

    all_groups = []
    if all_book_ids:
        all_files_query = File.query.filter(File.book_id.in_(all_book_ids)).all()
        all_groups = group_files_by_book(all_files_query, g.user.id)
    
    return render_template('_book_list.html', all_groups=all_groups, pagination=pagination, search_query=search_query)



if __name__ == '__main__':
    # 이 블록은 'python app.py'로 직접 실행할 때만 사용됩니다.
    # 로컬 테스트 및 디버깅 목적으로 남겨둡니다.
    app.run(debug=True, host='0.0.0.0', port=8000)
