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
        """Verify clean header, segmented control, hero continue card, and mobile tab bar render."""
        with self.client.session_transaction() as sess:
            user = User.query.filter_by(username="Gruzam").first()
            sess['user_id'] = user.id

        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # 1. Clean header & settings popover button
        self.assertIn('app-settings-btn', html)
        self.assertIn('app-settings-modal', html)

        # 2. iOS Segmented Controls
        self.assertIn('segmented-control', html)
        self.assertIn('data-tab="reading"', html)
        self.assertIn('data-tab="unread"', html)
        self.assertIn('data-tab="completed"', html)
        self.assertIn('data-tab="all"', html)

        # 3. Hero continue card
        self.assertIn('hero-continue-card', html)
        self.assertIn('hero-btn primary-btn', html)

        # 4. Unread Shuffle Recommendation Banner & Modal
        self.assertIn('unread-discovery-banner', html)
        self.assertIn('shuffle-recommend-modal', html)

        # 5. Mobile Floating Bottom Tab Bar
        self.assertIn('mobile-bottom-tab-bar', html)

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
