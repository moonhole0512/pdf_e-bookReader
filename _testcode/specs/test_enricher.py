import os
import sys
import unittest
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from models import db, User, Book, File
from services.book_enricher import clean_book_title, is_exact_volume_match, LibraryEnricher

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

if __name__ == '__main__':
    unittest.main()
