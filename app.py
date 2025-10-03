
import os
import re
from pathlib import Path
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, g, send_from_directory
from sqlalchemy import func, desc
from werkzeug.security import generate_password_hash, check_password_hash
from pypdf import PdfReader
import requests

from config import Config
from models import db, User, Book, File, ReadingState

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = User.query.get(user_id) if user_id is not None else None

def init_db():
    with app.app_context():
        # 설정에서 절대 DB 경로를 가져옵니다.
        db_path = app.config['DB_PATH']
        # 해당 경로의 디렉터리를 확인하고 생성합니다.
        db_dir = os.path.dirname(db_path)
        os.makedirs(db_dir, exist_ok=True)

        db.create_all()
        # Create a dummy user if not exists
        if not User.query.filter_by(username='dummy').first():
            dummy_user = User(username='dummy', password_hash=generate_password_hash('dummy'))
            db.session.add(dummy_user)
            db.session.commit()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('index'))
    return render_template('login.html')

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
    
    # --- 그룹화 로직 시작 ---
    def group_files_by_book(files):
        groups = {}
        for file in files:
            if file.book_id not in groups:
                groups[file.book_id] = []
            groups[file.book_id].append(file)
        
        grouped_list = []
        for book_id, file_list in groups.items():
            file_list.sort(key=lambda f: f.volume_number)
            cover_file = next((f for f in file_list if f.volume_number == 1), file_list[0])
            
            # Make files serializable for template
            serializable_files = []
            for f in file_list:
                serializable_files.append({
                    "id": f.id, 
                    "title": f.title or f.book.title, 
                    "author": f.author or f.book.author, 
                    "volume_number": f.volume_number, 
                    "cover_url": f.cover_url or f.book.cover_url
                })

            grouped_list.append({
                "book": file_list[0].book, # Representative book
                "files": serializable_files,
                "volume_count": len(file_list),
                "cover_file": cover_file
            })
        
        grouped_list.sort(key=lambda g: g['book'].title)
        return grouped_list

    # 2. 독서 중인 책 목록 (그룹화)
    reading_book_ids = db.session.query(File.book_id).join(ReadingState).filter(ReadingState.user_id == g.user.id).distinct()
    if last_read_state:
        reading_book_ids = reading_book_ids.filter(File.book_id != last_read_state.file.book_id)
    
    reading_files_query = File.query.filter(File.book_id.in_(reading_book_ids)).all()
    reading_groups = group_files_by_book(reading_files_query)

    # 3. 새로운 책 목록 (그룹화)
    read_book_ids = db.session.query(File.book_id).join(ReadingState).filter(ReadingState.user_id == g.user.id).distinct()
    new_files_query = File.query.filter(~File.book_id.in_(read_book_ids)).all()
    new_groups = group_files_by_book(new_files_query)

    # 4. 모든 책 목록 (그룹화)
    all_files_query = File.query.all()
    all_groups = group_files_by_book(all_files_query)

    return render_template('index.html', 
                           last_read_file=last_read_state.file if last_read_state else None,
                           reading_groups=reading_groups,
                           new_groups=new_groups,
                           all_groups=all_groups)

@app.route('/reader/<int:file_id>')
def reader(file_id):
    if not g.user:
        return redirect(url_for('login'))
        
    file = File.query.get_or_404(file_id)
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
        return jsonify({'next_file_id': None}), 404

@app.route('/admin/scan', methods=['GET']) # Should be POST in production with auth
def scan_files():
    pdf_root = app.config['PDF_ROOT_PATH']
    if not pdf_root or not os.path.exists(pdf_root):
        return jsonify({"error": "PDF_ROOT_PATH is not configured or does not exist."}), 500

    added_files = []
    existing_files = {f.file_path for f in File.query.all()}

    for pdf_path in Path(pdf_root).rglob('*.pdf'):
        pdf_path_str = str(pdf_path)
        if pdf_path_str in existing_files:
            continue

        try:
            # Extract metadata from filename (e.g., "Book Title - 01.pdf")
            filename = pdf_path.stem
            match = re.match(r'(.*?)(?: - |_)(\d+)$', filename)
            if match:
                title, volume_str = match.groups()
                volume = int(volume_str)
            else:
                title = filename
                volume = 1
            
            title = title.strip()

            # Get or create book
            book = Book.query.filter_by(title=title).first()
            if not book:
                book = Book(title=title, author="Unknown") # Default author
                db.session.add(book)
                db.session.flush() # To get book.id

            # Get page count
            reader = PdfReader(pdf_path_str)
            total_pages = len(reader.pages)

            # Create file entry
            new_file = File(
                book_id=book.id,
                file_path=pdf_path_str,
                volume_number=volume,
                total_pages=total_pages,
                title=book.title,  # Copy from parent book
                author=book.author # Copy from parent book
            )
            db.session.add(new_file)
            added_files.append(pdf_path_str)

        except Exception as e:
            app.logger.error(f"Failed to process {pdf_path_str}: {e}")

    # Update total_volumes for each book
    books_to_update = db.session.query(Book.id).join(File).filter(File.file_path.in_(added_files)).distinct()
    for book_id_tuple in books_to_update:
        book_id = book_id_tuple[0]
        count = db.session.query(func.count(File.id)).filter_by(book_id=book_id).scalar()
        book_to_update = Book.query.get(book_id)
        book_to_update.total_volumes = count

    db.session.commit()
    return jsonify({"message": f"Scan complete. Added {len(added_files)} new files.", "files": added_files})

@app.route('/admin/metadata/update', methods=['POST'])
def update_metadata():
    data = request.json
    book_id = data.get('book_id')
    title = data.get('title')
    author = data.get('author')

    book = Book.query.get_or_404(book_id)
    if title: book.title = title
    if author: book.author = author
    db.session.commit()

    return jsonify({"success": True, "message": "Metadata updated."})

@app.route('/api/book/lookup')
def lookup_book():
    isbn = request.args.get('isbn')
    if not isbn:
        return jsonify({"error": "ISBN is required"}), 400

    try:
        # Google Books API 호출
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if not data.get('items'):
            return jsonify({"error": "Book not found"}), 404

        volume_info = data['items'][0]['volumeInfo']
        result = {
            "title": volume_info.get('title'),
            "author": ", ".join(volume_info.get('authors', [])),
            "thumbnail": volume_info.get('imageLinks', {}).get('thumbnail'),
            "alt_images": []
        }

        # 썸네일이 없을 경우 Google 이미지 검색 (주의: 이 방식은 불안정할 수 있습니다)
        if not result['thumbnail']:
            # Gemini를 이용한 웹 검색으로 대체 이미지 URL을 찾습니다.
            # 실제 구현에서는 웹 스크래핑 라이브러리나 정식 이미지 검색 API 사용을 권장합니다.
            # 여기서는 예시로 간단한 검색 결과 링크를 파싱합니다.
            pass # Google 검색 기능은 현재 Tool에서 직접 호출할 수 없으므로, 이 부분은 비워둡니다.
                 # 대신 프론트엔드에서 사용자에게 이미지 URL을 직접 입력받는 방식을 고려할 수 있습니다.

        return jsonify(result)

    except requests.exceptions.RequestException as e:
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0')
