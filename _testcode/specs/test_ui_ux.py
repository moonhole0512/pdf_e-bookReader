import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from models import db, User, Book, File, ReadingState
from services.book_service import group_files_by_book

class TestUIUXEnhancements(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_group_reading_status_computation(self):
        """Verify group_files_by_book calculates reading, unread, and completed statuses correctly."""
        user = User.query.filter_by(username="Gruzam").first()
        self.assertIsNotNone(user)

        files = File.query.all()
        groups = group_files_by_book(files, user.id)
        self.assertGreater(len(groups), 0)

        statuses = {g['status'] for g in groups}
        self.assertTrue('reading' in statuses or 'unread' in statuses, "Must classify into reading or unread")
        for g in groups:
            self.assertIn(g['status'], ['reading', 'unread', 'completed'])

    def test_index_renders_ui_ux_components(self):
        """Verify header, bookshelf, continue reading, next volume button, and shuffle modal render."""
        with self.client.session_transaction() as sess:
            user = User.query.filter_by(username="Gruzam").first()
            sess['user_id'] = user.id

        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # 1. Header with action buttons
        self.assertIn('auto-enrich-btn', html)
        self.assertIn('scan-pdf-btn', html)

        # 2. Book grid & cards intact
        self.assertIn('book-grid', html)
        self.assertIn('book-card', html)

        # 3. Continue reading section
        self.assertIn('이어 읽기', html)

        # 4. Unread Shuffle Recommendation Mini Button & Modal
        self.assertIn('shuffle-pick-btn', html)
        self.assertIn('shuffle-recommend-modal', html)

        # 5. Core modals
        self.assertIn('isbn-modal', html)
        self.assertIn('volume-select-modal', html)

    def test_next_volume_api_with_metadata(self):
        """Verify /api/next_volume/<file_id> returns next volume number and title."""
        with self.client.session_transaction() as sess:
            user = User.query.filter_by(username="Gruzam").first()
            sess['user_id'] = user.id

        # Find a multi-volume book (e.g. 농림 or 냐루코양)
        vol1_file = File.query.filter_by(volume_number=1).filter(File.book_id.isnot(None)).first()
        self.assertIsNotNone(vol1_file)

        resp = self.client.get(f'/api/next_volume/{vol1_file.id}')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        if data.get('next_file_id'):
            self.assertEqual(data.get('next_volume_number'), 2)
            self.assertTrue(len(data.get('next_title', '')) > 0)

if __name__ == '__main__':
    unittest.main()
