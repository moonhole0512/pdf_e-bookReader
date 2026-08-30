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

        # 6. Library Sorting & View Mode Controls
        self.assertIn('shelf-sort-select', html)
        self.assertIn('view-mode-grid-btn', html)
        self.assertIn('view-mode-list-btn', html)
        self.assertIn('data-target-url', html)

    def test_next_volume_api_with_metadata(self):
        """Verify /api/next_volume/<file_id> returns next volume number and title."""
        with self.client.session_transaction() as sess:
            user = User.query.filter_by(username="Gruzam").first()
            sess['user_id'] = user.id

        vol1_file = File.query.filter_by(volume_number=1).filter(File.book_id.isnot(None)).first()
        self.assertIsNotNone(vol1_file)

        resp = self.client.get(f'/api/next_volume/{vol1_file.id}')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        if data.get('next_file_id'):
            self.assertEqual(data.get('next_volume_number'), 2)
            self.assertTrue(len(data.get('next_title', '')) > 0)

    def test_reader_touch_zones_and_scrubber_and_toc(self):
        """Verify reader view contains 3-way touch navigation zones, timeline scrubber, and TOC sidebar."""
        with self.client.session_transaction() as sess:
            user = User.query.filter_by(username="Gruzam").first()
            sess['user_id'] = user.id

        file_obj = File.query.first()
        self.assertIsNotNone(file_obj)

        resp = self.client.get(f'/reader/{file_obj.id}')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # Touch & click navigation zones
        self.assertIn('reader-touch-zones', html)
        self.assertIn('zone-prev', html)
        self.assertIn('zone-center', html)
        self.assertIn('zone-next', html)

        # Bottom scrubber
        self.assertIn('reader-scrubber-container', html)
        self.assertIn('scrubber-track', html)

        # TOC sidebar drawer
        self.assertIn('toc-sidebar', html)
        self.assertIn('toc-toggle-btn', html)
        self.assertIn('fullscreen-toggle-btn', html)

    def test_multi_card_reading_lounge_up_to_3_books(self):
        """Verify the Now Reading Lounge renders up to 3 recent reading cards in a responsive grid."""
        with self.client.session_transaction() as sess:
            user = User.query.filter_by(username="Gruzam").first()
            sess['user_id'] = user.id

        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # Confirm reading lounge section and responsive grid presence
        self.assertIn('reading-lounge-section', html)
        self.assertIn('reading-lounge-grid', html)
        self.assertIn('reading-lounge-card', html)

    def test_file_update_api_and_book_sync(self):
        """Verify /api/file/update saves title, author, and cover, synchronizing parent Book."""
        from models import Book, File
        with self.client.session_transaction() as sess:
            user = User.query.filter_by(username="Gruzam").first()
            sess['user_id'] = user.id

        # Create an isolated temporary test Book and File to prevent touching live books
        test_book = Book(title="Temp Test Book", author="Temp Author")
        db.session.add(test_book)
        db.session.commit()

        test_file = File(book_id=test_book.id, file_path="temp_test_file_unique_path.pdf", volume_number=1)
        db.session.add(test_file)
        db.session.commit()

        try:
            new_title = "Updated Test Title 1"
            new_author = "Updated Test Author"
            new_cover = "https://image.aladin.co.kr/product/test_cover500.jpg"

            resp = self.client.post('/api/file/update', json={
                'file_id': test_file.id,
                'title': new_title,
                'author': new_author,
                'cover_url': new_cover
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data.get('success'))
            self.assertEqual(data['file']['title'], new_title)
            self.assertEqual(data['file']['author'], new_author)
            self.assertEqual(data['file']['cover_url'], new_cover)

            # Check DB persistence
            reloaded_file = db.session.get(File, test_file.id)
            self.assertEqual(reloaded_file.title, new_title)
            self.assertEqual(reloaded_file.cover_url, new_cover)
            self.assertIsNotNone(reloaded_file.book)
            self.assertEqual(reloaded_file.book.cover_url, new_cover)
        finally:
            # Clean up temporary test data cleanly
            db.session.delete(test_file)
            db.session.delete(test_book)
            db.session.commit()

    def test_pagination_clean_url_and_safe_reload(self):
        """Verify pagination links target root URL and direct /api/books navigation redirects safely."""
        with self.client.session_transaction() as sess:
            user = User.query.filter_by(username="Gruzam").first()
            sess['user_id'] = user.id

        # 1. Direct browser navigation to /api/books?page=2 must redirect to /?page=2
        resp_direct = self.client.get('/api/books?page=2', headers={
            'Sec-Fetch-Dest': 'document',
            'Accept': 'text/html'
        })
        self.assertEqual(resp_direct.status_code, 302)
        self.assertIn('/?page=2', resp_direct.headers.get('Location', ''))

        # 2. AJAX fetch returns book-list fragment with 200 OK
        resp_ajax = self.client.get('/api/books?page=2', headers={
            'X-Requested-With': 'XMLHttpRequest'
        })
        self.assertEqual(resp_ajax.status_code, 200)
        html_ajax = resp_ajax.get_data(as_text=True)
        # Pagination links must target /?page= instead of /api/books
        self.assertNotIn('/api/books?page=', html_ajax)

        # 3. Reloading main page with page query param (?page=2) renders complete layout
        resp_page2 = self.client.get('/?page=2')
        self.assertEqual(resp_page2.status_code, 200)
        html_page2 = resp_page2.get_data(as_text=True)
        self.assertIn('reading-lounge-section', html_page2)
        self.assertIn('all-books-section', html_page2)

if __name__ == '__main__':
    unittest.main()
