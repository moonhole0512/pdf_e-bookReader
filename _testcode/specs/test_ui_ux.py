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

        # Modern glassmorphic floating pill dock controls (list, zoom-out, zoom-in, settings)
        self.assertIn('floating-controls', html)
        self.assertIn('reader-floating-dock', html)
        self.assertIn('settings-btn', html)
        self.assertIn('zoom-in', html)
        self.assertIn('zoom-out', html)
        self.assertIn('list-btn', html)

        # Unneeded buttons and drawer removed per user request (ponytail: YAGNI)
        self.assertNotIn('toc-sidebar', html)
        self.assertNotIn('toc-toggle-btn', html)
        self.assertNotIn('fullscreen-toggle-btn', html)
        self.assertNotIn('fab-toggle-btn', html)

    def test_multi_card_reading_lounge_up_to_4_books(self):
        """Verify the Now Reading Lounge renders up to 4 recent reading cards in a responsive 2x2 grid."""
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

        # Confirm Korean-only badge and unified ISBN button (no clutter icons)
        self.assertIn('이어 읽기', html)
        self.assertNotIn('📖 이어 읽기', html)
        self.assertNotIn('NOW READING', html)
        self.assertIn('lounge-isbn-btn', html)
        self.assertNotIn('ISBN 정보 수정', html)
        self.assertIn('series-view-btn', html)
        self.assertIn('시리즈 보기', html)
        self.assertNotIn('다음 권:', html)

        # Confirm CSS supports count-4 and 2x2 grid
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.reading-lounge-grid.count-4 {', css)

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

    def test_reader_mobile_header_stacks_without_overlap(self):
        """Verify mobile reader title and control dock occupy separate rows."""
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        mobile_header_start = css.index('/* --- Mobile Reader Floating Dock & Header --- */')
        mobile_header_end = css.index('/* --- Added Enhancements:', mobile_header_start)
        mobile_header = css[mobile_header_start:mobile_header_end]

        self.assertIn('@media (max-width: 600px)', mobile_header)
        self.assertIn('right: 10px;', mobile_header)
        self.assertIn('max-width: none;', mobile_header)
        self.assertIn('top: calc(env(safe-area-inset-top) + 56px);', mobile_header)
        self.assertIn('left: 50%;', mobile_header)
        self.assertIn('transform: translateX(-50%);', mobile_header)
        self.assertIn('reader-controls-hidden', mobile_header)

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

    def test_reader_settings_modal_overlay(self):
        """Verify settings panel is rendered as a centered glassmorphic modal overlay with click-outside closing."""
        from models import File
        with self.client.session_transaction() as sess:
            user = User.query.filter_by(username="Gruzam").first()
            sess['user_id'] = user.id

        file_obj = File.query.first()
        self.assertIsNotNone(file_obj)

        resp = self.client.get(f'/reader/{file_obj.id}')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # 1. HTML Modal Overlay Structure
        self.assertIn('id="settings-modal-overlay"', html)
        self.assertIn('modal-overlay', html)
        self.assertIn('settings-modal-card', html)
        self.assertIn('id="close-settings-btn"', html)

        # 2. CSS Centered Modal Styling & No Sidebar Shift
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('#settings-modal-overlay {', css)
        self.assertIn('.settings-modal-card {', css)
        self.assertNotIn('shifted-for-panel', css)

        # 3. JavaScript Click-outside and close logic
        with open('static/js/reader.js', 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertIn('settingsModalOverlay', js)
        self.assertIn('closeSettings()', js)
        self.assertIn('e.target === settingsModalOverlay', js)

    def test_reader_scrubber_tooltip_and_dynamic_tracking(self):
        """Verify scrubber tooltip is hidden by default and dynamically tracks mouse/touch during scrubbing."""
        from models import File
        with self.client.session_transaction() as sess:
            user = User.query.filter_by(username="Gruzam").first()
            sess['user_id'] = user.id

        file_obj = File.query.first()
        self.assertIsNotNone(file_obj)

        resp = self.client.get(f'/reader/{file_obj.id}')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # 1. HTML markup has empty tooltip with .hidden class (no static "p. 1" dummy text)
        self.assertIn('<div id="scrubber-tooltip" class="hidden"></div>', html)

        # 2. CSS contains hidden rules ensuring tooltip never leaks into idle reading view
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.hidden {\n    display: none !important;\n}', css)
        self.assertIn('#scrubber-tooltip.hidden {', css)

        # 3. JS tracks mouse and touch scrubbing dynamically
        with open('static/js/reader.js', 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertIn('function updateTooltip', js)
        self.assertIn('function hideTooltip', js)
        self.assertIn('updateScrubberUI()', js)

    def test_floating_dock_top_right_and_relative_zoom(self):
        """Verify floating dock is positioned top-right (no collision with bottom scrubber) and zoom operates relative to visible scale."""
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        # 1. Dock positioned at top-right, avoiding bottom scrubber bar
        self.assertIn('#floating-controls.reader-floating-dock {', css)
        dock_idx = css.index('#floating-controls.reader-floating-dock {')
        dock_block = css[dock_idx:dock_idx + 400]
        self.assertIn('top: 15px;', dock_block)
        self.assertIn('right: 20px;', dock_block)

        # 2. Relative zoom calculation in JavaScript
        with open('static/js/reader.js', 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertIn('let lastRenderedScale = scale;', js)
        self.assertIn('lastRenderedScale = currentScale;', js)
        self.assertIn('baseScale = (fitMode !== \'custom\' && lastRenderedScale > 0) ? lastRenderedScale : scale;', js)

        # 3. Zen / Immersion mode: controls fade upward in unison (-8px), no lingering bottom +12px override
        self.assertNotIn('transform: translateY(12px)', css)
        self.assertIn('transform: translateY(-8px) !important;', css)

    def test_volume_select_modal_ui_consistency_and_glassmorphism(self):
        """Verify volume select modal layout consistency, standardized progress slot, and ISBN buttons."""
        with open('templates/index.html', 'r', encoding='utf-8') as f:
            html = f.read()
        with open('static/js/library.js', 'r', encoding='utf-8') as f:
            js = f.read()
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        # 1. Modern markup structure in index.html
        self.assertIn('volume-modal-card', html)
        self.assertIn('volume-modal-header', html)
        self.assertIn('volume-modal-close-icon', html)
        self.assertIn('volume-modal-close-pill', html)

        # 2. Consistent card layout and progress slots in library.js
        self.assertIn('vol-progress-slot', js)
        self.assertIn('vol-card-footer', js)
        self.assertIn('vol-isbn-btn', js)
        self.assertIn('미독 (총', js)
        self.assertIn('volumeModalCloseIcon', js)

        # 3. Glassmorphic styling and alignment in style.css
        self.assertIn('.volume-modal-card {', css)
        self.assertIn('.vol-progress-slot {', css)
        self.assertIn('.vol-isbn-btn {', css)
        self.assertIn('.volume-modal-close-pill {', css)
        self.assertIn('min-height: 36px;', css)

    def test_isbn_search_loading_card_and_user_feedback(self):
        """Verify the rich informative loading card in ISBN modal with pulse visual and book context."""
        with open('static/js/library.js', 'r', encoding='utf-8') as f:
            js = f.read()
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        # 1. Loading UI components in JavaScript
        self.assertIn('renderSearchLoading', js)
        self.assertIn('isbn-search-loading-card', js)
        self.assertIn('search-pulse-visual', js)
        self.assertIn('search-pulse-core', js)
        self.assertIn('search-target-pill', js)
        self.assertIn('search-step-desc', js)
        self.assertIn('도서 정보 검색 중', js)

        # 2. Modern Glassmorphic & Pulse Animation styles in CSS
        self.assertIn('.isbn-search-loading-card {', css)
        self.assertIn('.search-pulse-visual {', css)
        self.assertIn('@keyframes radarPulse {', css)
        self.assertIn('.search-target-pill {', css)
        self.assertIn('.search-target-vol-badge {', css)
        self.assertIn('.search-step-desc {', css)

    def test_icon_cleanup_and_status_chip_modernization(self):
        """Verify icons are removed from ISBN, reading status, and continue reading, while chips use sleek SVG icons."""
        with open('templates/index.html', 'r', encoding='utf-8') as f:
            index_html = f.read()
        with open('templates/_book_list.html', 'r', encoding='utf-8') as f:
            list_html = f.read()
        with open('static/js/library.js', 'r', encoding='utf-8') as f:
            js = f.read()
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        # 1. Icons removed from ISBN, 읽는 중, 이어 읽기
        self.assertNotIn('<h2>📖 이어 읽기</h2>', index_html)
        self.assertIn('<h2>이어 읽기</h2>', index_html)
        self.assertNotIn('<div class="lounge-badge">📖 이어 읽기</div>', index_html)
        self.assertIn('<div class="lounge-badge">이어 읽기</div>', index_html)

        # No book emoji in reading badge
        self.assertNotIn('📖 읽는 중', list_html)
        self.assertIn('읽는 중', list_html)
        self.assertNotIn('📖 읽는 중', js)

        # No SVG icon inside ISBN buttons
        self.assertIn('lounge-isbn-btn', index_html)
        self.assertIn('>ISBN</button>', index_html)
        self.assertIn('>ISBN</button>', js)

        # 2. Sleek SVG icons for unread and completed chips in shelf filter
        self.assertIn('data-filter="reading">읽는 중</button>', index_html)
        self.assertIn('data-filter="unread">', index_html)
        self.assertIn('data-filter="completed">', index_html)
        self.assertNotIn('🎲 미독 도서', index_html)
        self.assertNotIn('🏆 완독 도서', index_html)
        self.assertIn('chip-svg-icon', index_html)
        self.assertIn('.chip-svg-icon {', css)

        # 3. Clean completed checkmark in list badges (no trophy emoji)
        self.assertNotIn('완독 🏆', list_html)
        self.assertIn('완독 ✓', list_html)

    def test_mobile_responsive_full_width_and_uniform_book_sizes(self):
        """Verify mobile CSS guarantees full width, overflow prevention, and uniform book card sizes across rows."""
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        # 1. Global horizontal overflow prevention
        self.assertIn('overflow-x: hidden;', css)

        # 2. Cleaned legacy conflicting grid queries
        self.assertNotIn('minmax(120px, 1fr)', css)

        # 3. Mobile (< 600px) pixel-perfect 2-column uniform book grid
        self.assertIn('grid-template-columns: repeat(2, minmax(0, 1fr)) !important;', css)
        self.assertIn('aspect-ratio: 1 / 1.45 !important;', css)

        # 4. Mobile full-width reading lounge cards
        self.assertIn('grid-template-columns: 1fr !important; /* Full-width cards for mobile */', css)

        # 5. Mobile search input overflow prevention
        self.assertIn('min-width: 0 !important;', css)

    def test_reader_fit_width_scroll_and_touch_preservation(self):
        """Verify reader allows smooth scrolling when zoomed in fit-width mode on desktop and mobile."""
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()
        with open('static/js/reader.js', 'r', encoding='utf-8') as f:
            js = f.read()

        # 1. CSS Scroll Container & Touch Action
        self.assertIn('overflow-y: auto;', css)
        self.assertIn('touch-action: pan-y;', css)
        self.assertIn('-webkit-overflow-scrolling: touch;', css)

        # 2. Release touch-zone pointer-events on mobile to allow native vertical drag scrolling
        self.assertIn('.touch-zone {', css)
        self.assertIn('pointer-events: none !important;', css)

        # 3. Mouse wheel forwarding on touch zones for desktop
        self.assertIn("touchZonesWrapper.addEventListener('wheel'", js)
        self.assertIn('container.scrollTop += e.deltaY;', js)

        # 4. Mobile scroll vs tap separation in touch gestures
        self.assertIn('isTouchScrolling', js)
        self.assertIn('touchDuration < 350', js)
        self.assertIn('leftBoundary = screenWidth * 0.25;', js)
        self.assertIn('rightBoundary = screenWidth * 0.75;', js)

    def test_reader_title_display_and_series_view_button(self):
        """Verify book title is displayed in reader menu and lounge displays series-view-btn."""
        with open('templates/reader.html', 'r', encoding='utf-8') as f:
            reader_html = f.read()
        with open('templates/index.html', 'r', encoding='utf-8') as f:
            index_html = f.read()
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()
        with open('static/js/library.js', 'r', encoding='utf-8') as f:
            js = f.read()

        # 1. Reader displays book title and volume tag in header info pill
        self.assertIn('class="reader-info-pill"', reader_html)
        self.assertIn('class="reader-book-title"', reader_html)
        self.assertIn('{{ file.book.title }}', reader_html)
        self.assertIn('class="reader-vol-badge"', reader_html)
        self.assertIn('.reader-book-title {', css)
        self.assertIn('.reader-vol-badge {', css)

        # 2. Lounge displays "시리즈 보기" without icons and without "다음 권"
        self.assertIn('series-view-btn', index_html)
        self.assertIn('>시리즈 보기</button>', index_html)
        self.assertNotIn('다음 권:', index_html)
        self.assertNotIn('⏭️', index_html)

        # 3. library.js supports opening volume select modal on series-view-btn click
        self.assertIn("e.target.closest('.series-view-btn')", js)
        self.assertIn('openVolumeModal(seriesBtn);', js)

    def test_reader_canvas_centering_on_zoom_out(self):
        """Verify #reader-container and #pdf-viewer center canvas vertically and horizontally when scaled down."""
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        # 1. Flex container layout for vertical centering
        self.assertIn('display: flex;', css)
        self.assertIn('flex-direction: column;', css)
        self.assertIn('align-items: center;', css)

        # 2. #pdf-viewer margin: auto for centering when smaller and top-anchored when larger
        self.assertIn('margin: auto;', css)
        self.assertIn('#pdf-viewer {', css)

    def test_reader_image_copy_and_save_action_menu(self):
        """Verify image action menu for right-click copy and save in reader mode."""
        with open('templates/reader.html', 'r', encoding='utf-8') as f:
            html = f.read()
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()
        with open('static/js/reader.js', 'r', encoding='utf-8') as f:
            js = f.read()

        # 1. Markup checks in reader.html
        self.assertIn('id="image-action-menu"', html)
        self.assertIn('id="img-action-copy"', html)
        self.assertIn('id="img-action-save"', html)
        self.assertIn('id="img-action-open"', html)
        self.assertIn('id="reader-toast"', html)

        # 2. CSS checks
        self.assertIn('.image-action-menu {', css)
        self.assertIn('z-index: 10000;', css)
        self.assertIn('.reader-toast {', css)

        # 3. JS checks: right click contextmenu, mobile longpress, clipboard copy, save
        self.assertIn("container.addEventListener('contextmenu'", js)
        self.assertIn("touchZonesWrapper.addEventListener('contextmenu'", js)
        self.assertIn('navigator.clipboard.write', js)
        self.assertIn('showReaderToast(', js)
        self.assertIn('longPressTimer', js)

    def test_hybrid_page_management_virtual_staging_and_client_commit(self):
        """Verify hybrid page management: virtual staging in reader and client-side pdf-lib commit."""
        from models import PageEdit
        import inspect

        # 1. Model inspection
        self.assertTrue(hasattr(PageEdit, 'file_id'))
        self.assertTrue(hasattr(PageEdit, 'page_num'))
        self.assertTrue(hasattr(PageEdit, 'action'))
        self.assertTrue(hasattr(PageEdit, 'image_path'))
        self.assertTrue(hasattr(PageEdit, 'to_dict'))

        # 2. Template verification
        with open('templates/reader.html', 'r', encoding='utf-8') as f:
            reader_html = f.read()
        self.assertIn('id="img-action-replace"', reader_html)
        self.assertIn('id="img-action-delete"', reader_html)
        self.assertIn('id="img-action-cancel-edit"', reader_html)
        self.assertIn('id="page-replace-file-input"', reader_html)

        with open('templates/index.html', 'r', encoding='utf-8') as f:
            index_html = f.read()
        self.assertIn('pdf-lib.min.js', index_html)
        self.assertIn('id="pending-edits-btn"', index_html)
        self.assertIn('id="pending-edits-modal"', index_html)
        self.assertIn('id="commit-all-edits-btn"', index_html)

        # 3. CSS verification
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.pending-edits-btn {', css)
        self.assertIn('.pending-edits-card {', css)
        self.assertIn('.commit-all-edits-btn {', css)
        self.assertIn('.image-action-divider {', css)

        # 4. Reader JS virtual map & override rendering verification
        with open('static/js/reader.js', 'r', encoding='utf-8') as f:
            reader_js = f.read()
        self.assertIn('buildVirtualPageMap', reader_js)
        self.assertIn('fetchAndApplyPageEdits', reader_js)
        self.assertIn('/api/page/override_image/', reader_js)
        self.assertIn('imgActionReplaceBtn', reader_js)
        self.assertIn('imgActionDeleteBtn', reader_js)

        # 5. Library JS client-side pdf-lib commit verification
        with open('static/js/library.js', 'r', encoding='utf-8') as f:
            lib_js = f.read()
        self.assertIn('/api/page/pending_edits', lib_js)
        self.assertIn('PDFLib.PDFDocument.load', lib_js)
        self.assertIn('/api/file/replace_pdf', lib_js)

        # 6. Backend API response check
        user = User.query.filter_by(username="Gruzam").first()
        with self.client.session_transaction() as sess:
            sess['user_id'] = user.id
        resp = self.client.get('/api/page/pending_edits')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('total_count', data)

    def test_image_action_menu_backdrop_dismiss_without_side_effects(self):
        """Verify image action menu transparent backdrop dismisses cleanly without triggering page turns or toggles."""
        with open('templates/reader.html', 'r', encoding='utf-8') as f:
            reader_html = f.read()
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()
        with open('static/js/reader.js', 'r', encoding='utf-8') as f:
            js = f.read()

        # 1. Backdrop Markup in reader.html
        self.assertIn('id="image-action-backdrop"', reader_html)
        self.assertIn('class="image-action-backdrop hidden"', reader_html)

        # 2. Backdrop CSS (z-index 9999 right below menu 10000)
        self.assertIn('.image-action-backdrop {', css)
        self.assertIn('z-index: 9999;', css)
        self.assertIn('inset: 0;', css)

        # 3. JS Backdrop safe dismissal and timestamp suppression
        self.assertIn('imageActionBackdrop', js)
        self.assertIn('dismissImageMenuSafely', js)
        self.assertIn('menuDismissTimestamp', js)
        self.assertIn('Date.now() - menuDismissTimestamp < 250', js)

    def test_reader_renders_hidpi_canvas_without_css_upscaling(self):
        """Verify PDF and replacement-image canvases render at device pixel density."""
        with open('static/js/reader.js', 'r', encoding='utf-8') as f:
            js = f.read()

        # The helper must keep layout dimensions in CSS pixels while increasing
        # the backing bitmap for Retina/mobile displays.
        self.assertIn('function configureHiDPICanvas(canvas, cssWidth, cssHeight)', js)
        self.assertIn('window.devicePixelRatio || 1', js)
        self.assertIn('canvas.style.width = `${cssWidth}px`', js)
        self.assertIn('canvas.style.height = `${cssHeight}px`', js)

        # Both rendering paths must use the helper; PDF.js also needs the
        # matching transform so its viewport remains in CSS-pixel coordinates.
        self.assertIn('configureHiDPICanvas(canvas, cssWidth, cssHeight)', js)
        self.assertIn('configureHiDPICanvas(canvas, viewport.width, viewport.height)', js)
        self.assertIn('transform: outputScale !== 1', js)
        self.assertIn('[outputScale, 0, 0, outputScale, 0, 0]', js)

    def test_reader_page_turn_keeps_previous_canvas_until_rendered(self):
        """Verify page turns use off-screen rendering and atomic Canvas swaps."""
        with open('static/js/reader.js', 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn('let renderGeneration = 0;', js)
        self.assertIn('const generation = ++renderGeneration;', js)
        self.assertIn('if (generation !== renderGeneration) return;', js)
        self.assertIn('viewer.replaceChildren(readyCanvas);', js)
        self.assertIn('viewer.replaceChildren(readyCanvas2, readyCanvas1);', js)
        self.assertNotIn("viewer.innerHTML = '';", js)

    def test_reader_preloads_adjacent_pages_and_invalidates_cache(self):
        """Verify adjacent pages are warmed off-screen and stale cache is cleared."""
        with open('static/js/reader.js', 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn('const pageRenderCache = new Map();', js)
        self.assertIn('function getCachedPageCanvas(vNum)', js)
        self.assertIn('async function preloadAdjacentPages()', js)
        self.assertIn('function scheduleAdjacentPreload()', js)
        self.assertIn('renderPage(vNum, canvas, true)', js)
        self.assertIn('scheduleAdjacentPreload();', js)
        self.assertIn('let pageCacheRevision = 0;', js)
        self.assertIn('pageCacheRevision += 1;', js)
        self.assertGreaterEqual(js.count('clearPageRenderCache();'), 5)

if __name__ == '__main__':
    unittest.main()
