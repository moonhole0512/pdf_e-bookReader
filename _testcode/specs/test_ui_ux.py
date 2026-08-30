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
        self.assertIn('<polyline points="15 18 9 12 15 6">', html)
        self.assertIn('<polyline points="9 18 15 12 9 6">', html)

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

    def test_reader_controls_smooth_in_place_fade_transition(self):
        """Verify reader scrubber and page-indicator fade in-place without horizontal distortion."""
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        # 1. #reader-scrubber-container.reader-controls-hidden MUST retain translateX(-50%)
        # so it stays centered and does NOT jump sideways when fading
        self.assertIn('#reader-scrubber-container.reader-controls-hidden', css)
        scrubber_hidden_block = css[css.index('#reader-scrubber-container.reader-controls-hidden'):css.index('#reader-scrubber-container.reader-controls-hidden') + 200]
        self.assertIn('translateX(-50%)', scrubber_hidden_block)

        # 2. #page-indicator.reader-controls-hidden MUST NOT have translateX
        # so it stays anchored at top-left without jumping sideways
        page_ind_block = css[css.index('#page-indicator.reader-controls-hidden'):css.index('#page-indicator.reader-controls-hidden') + 200]
        self.assertNotIn('translateX', page_ind_block)
        self.assertIn('translateY', page_ind_block)

    def test_touch_zones_default_cursor_and_svg_centering(self):
        """Verify touch zones keep default cursor and zone hints use centered SVGs."""
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        # Check cursor is default on touch zones
        left_block = css[css.index('.touch-zone-left {'):css.index('.touch-zone-left {') + 100]
        self.assertIn('cursor: default;', left_block)
        right_block = css[css.index('.touch-zone-right {'):css.index('.touch-zone-right {') + 100]
        self.assertIn('cursor: default;', right_block)

        # Check zone-hint uses flex center for pixel-perfect centering
        hint_block = css[css.index('.zone-hint {'):css.index('.zone-hint {') + 600]
        self.assertIn('display: flex;', hint_block)
        self.assertIn('align-items: center;', hint_block)
        self.assertIn('justify-content: center;', hint_block)

        # Check zone-hint is hidden on mobile/touch screens to avoid occluding book text
        mobile_idx = css.index('Hide touch zone chevron hints')
        self.assertIn('display: none !important;', css[mobile_idx:mobile_idx + 250])

    def test_reader_sharpen_filter_options(self):
        """Verify reader contains GPU-accelerated SVG sharpen filters and 3-step UI button group."""
        from models import File
        with self.client.session_transaction() as sess:
            user = User.query.filter_by(username="Gruzam").first()
            sess['user_id'] = user.id

        file_obj = File.query.first()
        self.assertIsNotNone(file_obj)

        resp = self.client.get(f'/reader/{file_obj.id}')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # 1. Native SVG sharpen filter definitions
        self.assertIn('id="sharpen-filter-mild"', html)
        self.assertIn('id="sharpen-filter-strong"', html)
        self.assertIn('feConvolveMatrix', html)

        # 2. UI button group in reader settings panel
        self.assertIn('id="sharpen-button-group"', html)
        self.assertIn('id="sharpen-off"', html)
        self.assertIn('id="sharpen-mild"', html)
        self.assertIn('id="sharpen-strong"', html)

        # 3. JavaScript integration
        with open('static/js/reader.js', 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertIn('SHARPEN_KEY', js)
        self.assertIn('url(#sharpen-filter-mild)', js)
        self.assertIn('url(#sharpen-filter-strong)', js)

if __name__ == '__main__':
    unittest.main()
