import os
import sqlite3
import logging

logger = logging.getLogger(__name__)


BOOK_METADATA_COLUMNS = (
    ('isbn_13', 'VARCHAR(13)'),
    ('source_category', 'VARCHAR(255)'),
    ('category', 'VARCHAR(50)'),
    ('metadata_source', 'VARCHAR(50)'),
)


def _table_exists(cursor, table_name):
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _index_names(cursor, table_name):
    cursor.execute(f"PRAGMA index_list({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _has_single_file_unique_constraint(cursor):
    """Return whether reading_state still has the legacy UNIQUE(file_id)."""
    if not _table_exists(cursor, 'reading_state'):
        return False

    cursor.execute("PRAGMA index_list(reading_state)")
    for index_row in cursor.fetchall():
        # PRAGMA index_list columns: seq, name, unique, origin, partial
        if not index_row[2]:
            continue
        index_name = index_row[1]
        cursor.execute(f"PRAGMA index_info({index_name})")
        index_columns = [row[2] for row in cursor.fetchall()]
        if index_columns == ['file_id']:
            return True
    return False


def _normalized_relative_path(raw_path, pdf_root_path):
    """Return the migration target for a stored path, or None if unchanged."""
    if not raw_path or not pdf_root_path:
        return None

    clean_path = raw_path.replace('\\', '/')
    normalized_pdf_root = os.path.abspath(pdf_root_path).replace('\\', '/').rstrip('/')
    rel_path = None

    if clean_path.startswith(normalized_pdf_root):
        rel_path = clean_path[len(normalized_pdf_root):].lstrip('/')
    elif '/pdfs/' in clean_path:
        rel_path = clean_path.split('/pdfs/')[-1].lstrip('/')
    elif os.path.isabs(raw_path):
        rel_path = os.path.basename(raw_path)

    if rel_path and rel_path != raw_path:
        return rel_path
    return None


def _pending_migrations(cursor, pdf_root_path):
    """List changes that this module would make to the existing database."""
    pending = []

    if _table_exists(cursor, 'user'):
        if 'is_admin' not in _table_columns(cursor, 'user'):
            pending.append("user.is_admin")

    if _table_exists(cursor, 'book'):
        book_columns = _table_columns(cursor, 'book')
        pending.extend(
            f"book.{name}" for name, _ in BOOK_METADATA_COLUMNS
            if name not in book_columns
        )

        book_indexes = _index_names(cursor, 'book')
        if 'ix_book_category' not in book_indexes:
            pending.append("book.ix_book_category")
        if 'ix_book_isbn_13' not in book_indexes:
            pending.append("book.ix_book_isbn_13")

        if 'category' in book_columns:
            cursor.execute(
                "SELECT 1 FROM book WHERE category IS NULL OR TRIM(category) = '' LIMIT 1"
            )
            if cursor.fetchone() is not None:
                pending.append("book.category_defaults")

    if _has_single_file_unique_constraint(cursor):
        pending.append("reading_state.user_file_constraint")

    if pdf_root_path and _table_exists(cursor, 'file'):
        cursor.execute("SELECT file_path FROM file")
        if any(_normalized_relative_path(row[0], pdf_root_path) for row in cursor.fetchall()):
            pending.append("file.relative_paths")

    return pending


def _create_database_backup(conn, backup_path):
    """Create a consistent SQLite backup, including any active WAL contents."""
    with sqlite3.connect(backup_path) as backup_conn:
        conn.backup(backup_conn)


def migrate_database(db_path: str, pdf_root_path: str):
    """
    Safely migrates an existing SQLite database when changes are required:
    1. Checks the database before creating library.db.bak
    2. Backs up library.db only when a migration is pending
    2. Migrates reading_state table constraint to composite (user_id, file_id)
    3. Normalizes existing absolute file paths to POSIX relative paths
    4. Ensures user table has is_admin column and grants admin to existing users
    5. Adds compact book discovery metadata columns on existing libraries
    """
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Enable WAL mode and timeout on connection
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")

        pending = _pending_migrations(cursor, pdf_root_path)
        if not pending:
            logger.info("Database migration not required; skipping backup and migration.")
            return

        logger.info("Database migration required: %s", ', '.join(pending))
        backup_path = f"{db_path}.bak"
        try:
            _create_database_backup(conn, backup_path)
            logger.info(f"Created database backup at {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to create database backup: {e}")

        # --- 1. User table migration ---
        user_columns = _table_columns(cursor, 'user') if _table_exists(cursor, 'user') else set()
        if 'is_admin' not in user_columns:
            logger.info("Adding 'is_admin' column to user table.")
            cursor.execute("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0 NOT NULL")
            # If there's an existing user, make them admin
            cursor.execute("UPDATE user SET is_admin = 1 WHERE id = 1")
            conn.commit()

        # --- 1b. Book metadata migration ---
        # Additive SQLite changes preserve every existing book and reading state.
        book_columns = _table_columns(cursor, 'book') if _table_exists(cursor, 'book') else set()
        for name, column_type in BOOK_METADATA_COLUMNS:
            if name not in book_columns:
                logger.info("Adding '%s' column to book table.", name)
                cursor.execute(f"ALTER TABLE book ADD COLUMN {name} {column_type}")
        if _table_exists(cursor, 'book'):
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_book_category ON book (category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_book_isbn_13 ON book (isbn_13)")
            # Every book must remain discoverable even if a provider has no matching record.
            cursor.execute("UPDATE book SET category = '미분류' WHERE category IS NULL OR TRIM(category) = ''")
            conn.commit()

        # --- 2. ReadingState table migration ---
        # Check if reading_state has unique(file_id) constraint
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='reading_state'")
        table_def_row = cursor.fetchone()
        if table_def_row:
            if _has_single_file_unique_constraint(cursor):
                logger.info("Migrating reading_state table to composite unique constraint (user_id, file_id)...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS reading_state_new (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        file_id INTEGER NOT NULL,
                        current_page INTEGER DEFAULT 1,
                        last_read_at DATETIME,
                        FOREIGN KEY(user_id) REFERENCES user(id),
                        FOREIGN KEY(file_id) REFERENCES file(id),
                        CONSTRAINT uq_user_file_reading_state UNIQUE (user_id, file_id)
                    )
                """)
                cursor.execute("""
                    INSERT OR IGNORE INTO reading_state_new (id, user_id, file_id, current_page, last_read_at)
                    SELECT id, user_id, file_id, current_page, last_read_at FROM reading_state
                """)
                cursor.execute("DROP TABLE reading_state")
                cursor.execute("ALTER TABLE reading_state_new RENAME TO reading_state")
                cursor.execute("CREATE INDEX IF NOT EXISTS ix_reading_state_user_id ON reading_state (user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS ix_reading_state_file_id ON reading_state (file_id)")
                conn.commit()
                logger.info("reading_state migration completed successfully.")

        # --- 3. Normalize File paths to Relative POSIX paths ---
        if pdf_root_path and _table_exists(cursor, 'file'):
            cursor.execute("SELECT id, file_path FROM file")
            rows = cursor.fetchall()

            updates = []
            for file_id, raw_path in rows:
                rel_path = _normalized_relative_path(raw_path, pdf_root_path)
                if rel_path and rel_path != raw_path:
                    updates.append((rel_path, file_id))

            if updates:
                logger.info(f"Normalizing {len(updates)} file paths to relative POSIX paths...")
                cursor.executemany("UPDATE file SET file_path = ? WHERE id = ?", updates)
                conn.commit()
                logger.info("File path normalization completed.")

        conn.commit()
        logger.info("Database migration check finished.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during database migration: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
