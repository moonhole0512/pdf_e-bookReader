import os
import sqlite3
import tempfile
import unittest

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from services.migration import migrate_database


class TestDatabaseMigration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_current_schema(self, db_path, file_path='book.pdf'):
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE user (
                id INTEGER PRIMARY KEY,
                username VARCHAR(80) NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT 0
            );
            CREATE TABLE book (
                id INTEGER PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                isbn_13 VARCHAR(13),
                source_category VARCHAR(255),
                category VARCHAR(50),
                metadata_source VARCHAR(50)
            );
            CREATE INDEX ix_book_category ON book (category);
            CREATE INDEX ix_book_isbn_13 ON book (isbn_13);
            CREATE TABLE file (
                id INTEGER PRIMARY KEY,
                book_id INTEGER NOT NULL,
                file_path VARCHAR(1024) NOT NULL
            );
            CREATE TABLE reading_state (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                file_id INTEGER NOT NULL,
                current_page INTEGER DEFAULT 1,
                last_read_at DATETIME,
                CONSTRAINT uq_user_file_reading_state UNIQUE (user_id, file_id)
            );
            """
        )
        conn.execute("INSERT INTO user (id, username, is_admin) VALUES (1, 'reader', 1)")
        conn.execute("INSERT INTO book (id, title, category) VALUES (1, 'Book', 'Novel')")
        conn.execute("INSERT INTO file (id, book_id, file_path) VALUES (1, 1, ?)", (file_path,))
        conn.commit()
        conn.close()

    def test_legacy_reading_state_constraint_is_migrated(self):
        db_path = os.path.join(self.temp_dir.name, 'legacy_reading.db')
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(80));
            CREATE TABLE book (id INTEGER PRIMARY KEY, title VARCHAR(255));
            CREATE TABLE file (id INTEGER PRIMARY KEY, file_path VARCHAR(1024));
            CREATE TABLE reading_state (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                file_id INTEGER NOT NULL UNIQUE,
                current_page INTEGER DEFAULT 1,
                last_read_at DATETIME
            );
            INSERT INTO user (id, username) VALUES (1, 'reader');
            INSERT INTO book (id, title) VALUES (1, 'Book');
            INSERT INTO file (id, file_path) VALUES (1, 'book.pdf');
            INSERT INTO reading_state (id, user_id, file_id, current_page)
                VALUES (1, 1, 1, 7);
            """
        )
        conn.commit()
        conn.close()

        migrate_database(db_path, self.temp_dir.name)

        conn = sqlite3.connect(db_path)
        unique_constraints = []
        for row in conn.execute("PRAGMA index_list(reading_state)").fetchall():
            if row[2]:
                index_name = row[1]
                unique_constraints.append([
                    column[2]
                    for column in conn.execute(f"PRAGMA index_info({index_name})").fetchall()
                ])
        state = conn.execute(
            "SELECT user_id, file_id, current_page FROM reading_state"
        ).fetchone()
        conn.close()

        self.assertIn(['user_id', 'file_id'], unique_constraints)
        self.assertNotIn(['file_id'], unique_constraints)
        self.assertEqual(state, (1, 1, 7))

    def test_absolute_file_paths_are_normalized_and_then_skipped(self):
        db_path = os.path.join(self.temp_dir.name, 'current.db')
        absolute_path = os.path.join(self.temp_dir.name, 'nested', 'book.pdf')
        self._create_current_schema(db_path, absolute_path)

        migrate_database(db_path, self.temp_dir.name)

        conn = sqlite3.connect(db_path)
        stored_path = conn.execute("SELECT file_path FROM file WHERE id = 1").fetchone()[0]
        conn.close()
        self.assertEqual(stored_path, 'nested/book.pdf')
        backup_path = f'{db_path}.bak'
        self.assertTrue(os.path.exists(backup_path))
        backup_mtime = os.stat(backup_path).st_mtime_ns

        migrate_database(db_path, self.temp_dir.name)

        self.assertEqual(os.stat(backup_path).st_mtime_ns, backup_mtime)


if __name__ == '__main__':
    unittest.main()
