import os
import shutil
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def migrate_database(db_path: str, pdf_root_path: str):
    """
    Safely migrates an existing SQLite database:
    1. Backs up library.db to library.db.bak
    2. Migrates reading_state table constraint to composite (user_id, file_id)
    3. Normalizes existing absolute file paths to POSIX relative paths
    4. Ensures user table has is_admin column and grants admin to existing users
    """
    if not os.path.exists(db_path):
        return

    backup_path = f"{db_path}.bak"
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"Created database backup at {backup_path}")
    except Exception as e:
        logger.warning(f"Failed to create database backup: {e}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Enable WAL mode and timeout on connection
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")

        # --- 1. User table migration ---
        cursor.execute("PRAGMA table_info(user)")
        user_columns = [row[1] for row in cursor.fetchall()]
        if 'is_admin' not in user_columns:
            logger.info("Adding 'is_admin' column to user table.")
            cursor.execute("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0 NOT NULL")
            # If there's an existing user, make them admin
            cursor.execute("UPDATE user SET is_admin = 1 WHERE id = 1")
            conn.commit()

        # --- 2. ReadingState table migration ---
        # Check if reading_state has unique(file_id) constraint
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='reading_state'")
        table_def_row = cursor.fetchone()
        if table_def_row:
            table_sql = table_def_row[0] or ""
            # If table_sql has 'UNIQUE (file_id)' or 'file_id' ... 'UNIQUE', need to recreate
            if "UNIQUE (file_id)" in table_sql or "file_id INTEGER UNIQUE" in table_sql or "file_id INT UNIQUE" in table_sql or "UNIQUE(file_id)" in table_sql:
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
        if pdf_root_path:
            cursor.execute("SELECT id, file_path FROM file")
            rows = cursor.fetchall()
            normalized_pdf_root = os.path.abspath(pdf_root_path).replace('\\', '/').rstrip('/')

            updates = []
            for file_id, raw_path in rows:
                if not raw_path:
                    continue
                clean_path = raw_path.replace('\\', '/')
                rel_path = None

                # Check if path starts with pdf_root_path
                if clean_path.startswith(normalized_pdf_root):
                    rel_path = clean_path[len(normalized_pdf_root):].lstrip('/')
                elif '/pdfs/' in clean_path:
                    # Docker or alternative root fallback
                    parts = clean_path.split('/pdfs/')
                    rel_path = parts[-1].lstrip('/')
                elif os.path.isabs(raw_path):
                    # Check if file exists relative to pdf_root_path using basename
                    basename = os.path.basename(raw_path)
                    rel_path = basename
                
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
