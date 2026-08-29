import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from models import db, User, Book, File, ReadingState

class TestE2ELiveData(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_existing_data_preserved(self):
        """Verify existing DB records (Gruzam user, books, files, reading state) are intact."""
        user = User.query.filter_by(username="Gruzam").first()
        self.assertIsNotNone(user, "Gruzam user must exist.")
        self.assertTrue(user.is_admin, "Gruzam should have admin privileges.")

        book_count = Book.query.count()
        self.assertGreaterEqual(book_count, 18, "At least 18 books should exist.")

        file_count = File.query.count()
        self.assertGreaterEqual(file_count, 29, "At least 29 files should exist.")

        # Check sample file path is normalized to relative POSIX
        first_file = File.query.first()
        self.assertFalse(os.path.isabs(first_file.file_path), f"File path should be relative, got {first_file.file_path}")

        # Check existing reading state
        state = ReadingState.query.filter_by(user_id=user.id).first()
        self.assertIsNotNone(state, "Reading state for Gruzam must be preserved.")
        self.assertEqual(state.current_page, 16)

    def test_index_page_flow(self):
        """Verify anonymous redirect and authenticated bookshelf render."""
        # 1. Anonymous access redirects to /login
        anon_resp = self.client.get('/')
        self.assertEqual(anon_resp.status_code, 302)
        self.assertIn('/login', anon_resp.headers['Location'])

        # 2. Login flow with Gruzam
        with self.client.session_transaction() as sess:
            user = User.query.filter_by(username="Gruzam").first()
            sess['user_id'] = user.id

        auth_resp = self.client.get('/')
        self.assertEqual(auth_resp.status_code, 200)
        content = auth_resp.get_data(as_text=True)
        self.assertIn("E-Book 라이브러리", content)
        self.assertIn("Gruzam", content)
        self.assertIn("이어 읽기", content)

    def test_reader_view_and_static_pdf_access(self):
        """Verify reader view renders correctly and static PDF endpoint serves safely."""
        user = User.query.filter_by(username="Gruzam").first()
        first_file = File.query.first()

        with self.client.session_transaction() as sess:
            sess['user_id'] = user.id

        reader_resp = self.client.get(f'/reader/{first_file.id}')
        self.assertEqual(reader_resp.status_code, 200)
        reader_html = reader_resp.get_data(as_text=True)
        self.assertIn("pdf-viewer", reader_html)
        self.assertIn(f'data-file-id="{first_file.id}"', reader_html)

    def test_scan_status_endpoint(self):
        """Verify admin scan status endpoint returns valid JSON."""
        user = User.query.filter_by(username="Gruzam").first()
        with self.client.session_transaction() as sess:
            sess['user_id'] = user.id

        status_resp = self.client.get('/api/admin/scan/status')
        self.assertEqual(status_resp.status_code, 200)
        status_data = status_resp.get_json()
        self.assertIn("state", status_data)

if __name__ == '__main__':
    unittest.main()
