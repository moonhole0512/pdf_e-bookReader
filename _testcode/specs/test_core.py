import os
import sys
import unittest
import tempfile
import sqlite3
from unittest.mock import patch
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from models import db, User, Book, File, ReadingState
from services.book_service import resolve_pdf_path, get_recommended_books, group_files_by_book
from services.scanner import LibraryScanner

class TestEBookReaderCore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_library.db")
        self.pdf_dir = os.path.join(self.temp_dir.name, "pdfs")
        os.makedirs(self.pdf_dir, exist_ok=True)

        # Create dummy PDF files
        self.sample_pdf = os.path.join(self.pdf_dir, "Test Book_01.pdf")
        with open(self.sample_pdf, "wb") as f:
            f.write(b"%PDF-1.4 header dummy file")

        class TestConfig:
            TESTING = True
            SECRET_KEY = "test-secret-key"
            DB_PATH = self.db_path
            PDF_ROOT_PATH = self.pdf_dir
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{self.db_path}"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            SQLALCHEMY_ENGINE_OPTIONS = {'connect_args': {'timeout': 5}}

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_sqlite_wal_pragma(self):
        """Verify SQLite connection uses WAL mode and busy_timeout."""
        engine = db.engine
        with engine.connect() as conn:
            journal_mode = conn.execute(db.text("PRAGMA journal_mode")).scalar()
            self.assertEqual(journal_mode.lower(), "wal")
            timeout = conn.execute(db.text("PRAGMA busy_timeout")).scalar()
            self.assertGreaterEqual(timeout, 5000)

    def test_multi_user_reading_state_integrity(self):
        """
        CRITICAL TEST: Verify multiple users can read the SAME book/file
        without UNIQUE constraint failure (fixes prior critical bug).
        """
        user1 = User(username="reader1")
        user2 = User(username="reader2")
        db.session.add_all([user1, user2])
        db.session.commit()

        book = Book(title="Shared Manga", author="Artist A")
        db.session.add(book)
        db.session.flush()

        file1 = File(book_id=book.id, file_path="manga_01.pdf", volume_number=1, total_pages=100)
        db.session.add(file1)
        db.session.commit()

        # User 1 reads file 1 to page 25
        state1 = ReadingState(user_id=user1.id, file_id=file1.id, current_page=25)
        db.session.add(state1)
        db.session.commit()

        # User 2 reads file 1 to page 50 (MUST NOT RAISE IntegrityError)
        state2 = ReadingState(user_id=user2.id, file_id=file1.id, current_page=50)
        db.session.add(state2)
        db.session.commit()

        # Verify independent reading progress
        s1 = ReadingState.query.filter_by(user_id=user1.id, file_id=file1.id).first()
        s2 = ReadingState.query.filter_by(user_id=user2.id, file_id=file1.id).first()
        self.assertEqual(s1.current_page, 25)
        self.assertEqual(s2.current_page, 50)

    def test_user_password_hashing(self):
        """Verify password set and verify behavior."""
        user = User(username="secure_user")
        user.set_password("MySecretPass123!")
        db.session.add(user)
        db.session.commit()

        self.assertNotEqual(user.password_hash, "MySecretPass123!")
        self.assertTrue(user.check_password("MySecretPass123!"))
        self.assertFalse(user.check_password("WrongPassword"))

    def test_portable_path_resolution(self):
        """Verify relative and absolute path resolution works across environments."""
        # 1. Relative POSIX path
        resolved = resolve_pdf_path(self.pdf_dir, "Test Book_01.pdf")
        self.assertIsNotNone(resolved)
        self.assertTrue(resolved.exists())
        self.assertEqual(resolved.resolve(), Path(self.sample_pdf).resolve())

        # 2. Legacy absolute path fallback
        resolved_abs = resolve_pdf_path(self.pdf_dir, self.sample_pdf)
        self.assertIsNotNone(resolved_abs)
        self.assertTrue(resolved_abs.exists())

    def test_auth_protection_on_static_pdfs(self):
        """SECURITY TEST: Unauthenticated requests to /pdfs/ must be blocked."""
        # Anonymous request
        resp = self.client.get('/pdfs/Test%20Book_01.pdf')
        # Should redirect to login or return 401
        self.assertIn(resp.status_code, (302, 401))

        # Logged in request
        with self.client.session_transaction() as sess:
            u = User(username="authed_user")
            db.session.add(u)
            db.session.commit()
            sess['user_id'] = u.id

        resp_auth = self.client.get('/pdfs/Test%20Book_01.pdf')
        self.assertEqual(resp_auth.status_code, 200)

    def test_background_scanner_and_group_by_volume_count(self):
        """Verify non-blocking scanner registers books and counts volumes accurately."""
        # Run scan synchronously inside test via _run_scan_thread
        metadata = {
            'title': 'Test Book', 'author': 'Author', 'cover_url': 'https://example.test/cover.jpg',
            'isbn': '9781234567890', 'source_category': 'Comics & Graphic Novels',
            'category': '만화', 'source': 'Google Books'
        }
        with patch('services.book_enricher.enrich_book_info', return_value=metadata):
            LibraryScanner._run_scan_thread(self.app, batch_size=10, clean_missing=False)

        # Check that file and book were created
        file_obj = File.query.filter_by(file_path="Test Book_01.pdf").first()
        self.assertIsNotNone(file_obj)
        self.assertEqual(file_obj.volume_number, 1)

        book = file_obj.book
        self.assertEqual(book.title, "Test Book")
        self.assertEqual(book.total_volumes, 1)
        self.assertEqual((book.isbn_13, book.source_category, book.category, book.metadata_source),
                         ('9781234567890', 'Comics & Graphic Novels', '만화', 'Google Books'))

        # Scanner status check
        status = LibraryScanner.get_status()
        self.assertEqual(status["state"], "completed")

    def test_reading_status_update_api(self):
        """Verify /api/status/update records page progress."""
        u = User(username="page_reader")
        b = Book(title="Page Turn Book")
        db.session.add_all([u, b])
        db.session.commit()

        f = File(book_id=b.id, file_path="turn_01.pdf", volume_number=1, total_pages=50)
        db.session.add(f)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user_id'] = u.id

        resp = self.client.post('/api/status/update', json={
            'file_id': f.id,
            'current_page': 12
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('success'))

        state = ReadingState.query.filter_by(user_id=u.id, file_id=f.id).first()
        self.assertIsNotNone(state)
        self.assertEqual(state.current_page, 12)

if __name__ == '__main__':
    unittest.main()
