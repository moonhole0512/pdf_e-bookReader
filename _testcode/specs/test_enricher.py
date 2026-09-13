import os
import sys
import unittest
import tempfile
from unittest.mock import patch, Mock
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from models import db, User, Book, File
from services.book_enricher import clean_book_title, is_exact_volume_match, extract_aladin_product_genre, fetch_aladin_metadata, LibraryEnricher
from services.migration import migrate_database

class TestBookEnricher(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_enrich.db")

        class TestConfig:
            TESTING = True
            SECRET_KEY = "test-secret"
            DB_PATH = self.db_path
            PDF_ROOT_PATH = self.temp_dir.name
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

    def test_clean_book_title(self):
        self.assertEqual(clean_book_title("농림_01.pdf"), "농림")
        self.assertEqual(clean_book_title("기어와라 냐루코 양_02"), "기어와라 냐루코 양")
        self.assertEqual(clean_book_title("던전에서..._12_Special.pdf"), "던전에서...")
        self.assertEqual(clean_book_title("早乙女姉妹は漫畵のためなら!？1(ジャンプコミックス)(コミック)"), "早乙女姉妹は漫畵のためなら")
        self.assertEqual(clean_book_title("葬送のフリーレン 01巻 [コミック]"), "葬送のフリーレン")

    def test_strict_volume_matching(self):
        """Verify strict volume matcher prevents false positives like 11, 16 when seeking vol 1."""
        # Seeking Volume 1
        self.assertTrue(is_exact_volume_match("농림 1", 1))
        self.assertTrue(is_exact_volume_match("농림 1권", 1))
        self.assertTrue(is_exact_volume_match("농림! 1", 1))
        self.assertFalse(is_exact_volume_match("농림 11", 1), "Should NOT match volume 11 as volume 1")
        self.assertFalse(is_exact_volume_match("나와 호랑이님 16", 1), "Should NOT match volume 16 as volume 1")
        self.assertFalse(is_exact_volume_match("농림 2", 1), "Should NOT match volume 2 as volume 1")

        # Seeking Volume 12
        self.assertTrue(is_exact_volume_match("던전에서 만남을 추구하면 안 되는 걸까 12", 12))
        self.assertFalse(is_exact_volume_match("던전에서 만남을 추구하면 안 되는 걸까 1", 12))

    def test_aladin_product_genre_is_preserved_without_remapping(self):
        search_html = '''<div class="ss_book_box" itemId="9204538"><a href="https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=9204538" class="bo3">나와 호랑이님 2</a><li>카넬 | 디앤씨미디어 | 2011년</li><div isbn="8926780678"></div></div>'''
        detail_html = '''<script type="application/ld+json">{"@type":"Book", "genre" : "라이트 노벨"}</script>'''
        with patch('services.book_enricher.requests.get', side_effect=[
            Mock(status_code=200, text=search_html), Mock(status_code=200, text=detail_html)
        ]):
            metadata = fetch_aladin_metadata('나와 호랑이님', volume=2)
        self.assertEqual(extract_aladin_product_genre(detail_html), '라이트 노벨')
        self.assertEqual(metadata['source_category'], '라이트 노벨')
        self.assertEqual(metadata['category'], '라이트 노벨')
        self.assertEqual(metadata['product_url'], 'https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=9204538')

    def test_google_fallback_preserves_provider_category_metadata(self):
        from services.books_api import _category_metadata, _isbn_metadata
        self.assertEqual(
            _category_metadata({'title': 'Example', 'categories': ['Comics & Graphic Novels']}),
            {'source_category': 'Comics & Graphic Novels', 'category': 'Comics & Graphic Novels', 'source': 'Google Books'}
        )
        self.assertEqual(_isbn_metadata('978-1-234567-89-0'), {'isbn_13': '9781234567890', 'isbn_10': None})

    def test_existing_database_gets_additive_category_columns(self):
        """Migration adds discovery fields without recreating an existing book table."""
        legacy_path = os.path.join(self.temp_dir.name, 'legacy.db')
        conn = __import__('sqlite3').connect(legacy_path)
        conn.execute('CREATE TABLE book (id INTEGER PRIMARY KEY, title VARCHAR(255) NOT NULL, author VARCHAR(255))')
        conn.execute("INSERT INTO book (id, title, author) VALUES (1, '기존 책', '기존 저자')")
        conn.execute('CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(80))')
        conn.execute('CREATE TABLE file (id INTEGER PRIMARY KEY, file_path VARCHAR(1024))')
        conn.commit()
        conn.close()

        migrate_database(legacy_path, self.temp_dir.name)
        conn = __import__('sqlite3').connect(legacy_path)
        columns = {row[1] for row in conn.execute('PRAGMA table_info(book)')}
        row = conn.execute('SELECT title, author, isbn_13, source_category, category, metadata_source FROM book WHERE id = 1').fetchone()
        conn.close()
        self.assertTrue({'isbn_13', 'source_category', 'category', 'metadata_source'}.issubset(columns))
        self.assertEqual(row, ('기존 책', '기존 저자', None, None, '미분류', None))

    def test_background_enricher_persists_provider_category_metadata(self):
        # Simulates an existing fully enriched book that needs only category backfill.
        book = Book(title='Metadata Test', author='Known Author', cover_url='https://example.test/old-cover.jpg',
                    category='미분류')
        db.session.add(book)
        db.session.commit()
        file_obj = File(book_id=book.id, file_path='metadata_test.pdf', volume_number=1)
        file_obj.author = 'Known Author'
        file_obj.cover_url = 'https://example.test/old-cover.jpg'
        db.session.add(file_obj)
        db.session.commit()
        metadata = {
            'title': 'Metadata Test', 'author': 'Author', 'cover_url': 'https://example.test/cover.jpg',
            'isbn': '9781234567890', 'source_category': 'Psychology', 'category': 'Psychology',
            'source': 'Google Books'
        }
        with patch('services.book_enricher.enrich_book_info', return_value=metadata):
            LibraryEnricher._run_enrich_thread(self.app, force_all=False)
        updated = db.session.get(Book, book.id)
        self.assertEqual((updated.isbn_13, updated.source_category, updated.category, updated.metadata_source),
                         ('9781234567890', 'Psychology', 'Psychology', 'Google Books'))

    def test_background_enricher_marks_unmatched_books_unclassified(self):
        book = Book(title='Unmatched Metadata Test', author='Unknown')
        db.session.add(book)
        db.session.commit()
        db.session.add(File(book_id=book.id, file_path='unmatched_metadata_test.pdf', volume_number=1))
        db.session.commit()
        with patch('services.book_enricher.enrich_book_info', return_value=None):
            LibraryEnricher._run_enrich_thread(self.app, force_all=False)
        self.assertEqual(db.session.get(Book, book.id).category, '미분류')

    def test_enrichment_api_endpoints(self):
        import time
        user = User(username="admin_user", is_admin=True)
        db.session.add(user)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user_id'] = user.id

        # Trigger enrichment
        resp = self.client.post('/api/admin/enrich', json={'force_all': False})
        self.assertIn(resp.status_code, (200, 409))
        data = resp.get_json()
        self.assertIn('status', data)

        # Status check
        status_resp = self.client.get('/api/admin/enrich/status')
        self.assertEqual(status_resp.status_code, 200)
        s_data = status_resp.get_json()
        self.assertIn('state', s_data)

        # Wait briefly for thread to finish on empty DB
        time.sleep(0.3)

    def test_isbn_exact_lookup_and_bypass_relevance(self):
        """Verify search_book_candidates and /api/book/lookup resolve exact ISBNs even for out-of-print books."""
        from services.book_enricher import search_book_candidates
        # 1. search_book_candidates with real light novel ISBN 9788926780534
        results = search_book_candidates("9788926780534")
        self.assertTrue(len(results) >= 1)
        first = results[0]
        self.assertEqual(first.get('isbn_13'), "9788926780534")
        self.assertIn("호랑이", first.get('title', ''))

        # 2. Test /api/book/lookup endpoint with login
        user = User(username="isbn_test_user", is_admin=False)
        db.session.add(user)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user_id'] = user.id

        resp = self.client.get('/api/book/lookup?isbn=9788926780534')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get('isbn_13'), "9788926780534")
        self.assertIsNotNone(data.get('thumbnail'))

    def test_foreign_and_japanese_book_candidate_search(self):
        """Verify Japanese and foreign books resolve accurately via Aladin Foreign/All target and Google Books error protection."""
        from services.book_enricher import search_book_candidates
        cands = search_book_candidates("早乙女姉妹は漫畵のためなら!？1(ジャンプコミックス)(コミック)", volume=1)
        self.assertGreater(len(cands), 0)
        top = cands[0]
        self.assertIn("早乙女姉妹", top['title'])
        self.assertIn("山本亮平", top['author'])
        self.assertEqual(top['isbn_13'], "9784088816180")
        self.assertTrue('amazon' in top['thumbnail'].lower() or 'cover' in top['thumbnail'].lower())

    def test_adult_and_foreign_cover_bypass_via_amazon_cdn(self):
        """Verify adult (19+) / restricted manga covers bypass domestic placeholders via Amazon CDN."""
        from services.book_enricher import resolve_bypass_cover_url, isbn_13_to_10
        # Check standard digit
        self.assertEqual(isbn_13_to_10("9784088816180"), "4088816188")
        # Check 'X' check digit (EAN 9780804429573 -> ISBN-10 080442957X)
        self.assertEqual(isbn_13_to_10("9780804429573"), "080442957X")
        # Ensure length is strictly 10 characters
        self.assertEqual(len(isbn_13_to_10("9780804429573")), 10)
        cover_url = resolve_bypass_cover_url("9784088816180")
        self.assertIsNotNone(cover_url)
        self.assertIn("images-amazon.com", cover_url)

if __name__ == '__main__':
    unittest.main()
