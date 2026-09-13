import os
import re
import time
import logging
import threading
from pathlib import Path
from typing import Dict, Any
from sqlalchemy import func

logger = logging.getLogger(__name__)

class LibraryScanner:
    """
    Lightweight, thread-safe background scanner optimized for low-spec NAS (512MB RAM).
    Uses standard threading to prevent blocking web requests.
    """
    _lock = threading.Lock()
    _is_running = False
    _status: Dict[str, Any] = {
        "state": "idle", # idle, running, completed, error
        "message": "준비 완료",
        "total_scanned": 0,
        "new_added": 0,
        "removed_count": 0,
        "current_file": "",
        "start_time": None,
        "duration_seconds": 0
    }

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        with cls._lock:
            status_copy = cls._status.copy()
            if cls._is_running and cls._status.get("start_time"):
                status_copy["duration_seconds"] = round(time.time() - cls._status["start_time"], 1)
            return status_copy

    @classmethod
    def start_scan(cls, app, batch_size=30, clean_missing=False, enrich_metadata=True) -> bool:
        """
        Starts the scanner in a background thread if not already running.
        Returns True if started, False if already in progress.
        """
        with cls._lock:
            if cls._is_running:
                logger.warning("Scan requested while a scan is already running.")
                return False

            cls._is_running = True
            cls._status = {
                "state": "running",
                "message": "PDF 파일 탐색 및 등록 중...",
                "total_scanned": 0,
                "new_added": 0,
                "removed_count": 0,
                "current_file": "",
                "start_time": time.time(),
                "duration_seconds": 0
            }

        thread = threading.Thread(
            target=cls._run_scan_thread,
            args=(app, batch_size, clean_missing, enrich_metadata),
            daemon=True
        )
        thread.start()
        return True

    @classmethod
    def _run_scan_thread(cls, app, batch_size: int, clean_missing: bool, enrich_metadata: bool = True):
        from models import db, Book, File

        with app.app_context():
            start_t = time.time()
            try:
                pdf_root_str = app.config.get('PDF_ROOT_PATH')
                if not pdf_root_str or not os.path.exists(pdf_root_str):
                    raise ValueError(f"PDF 루트 경로가 올바르지 않거나 존재하지 않습니다: {pdf_root_str}")

                pdf_root = Path(pdf_root_str).resolve()
                logger.info(f"Background scan started on: {pdf_root}")

                # 1. Collect all existing files from DB (both relative posix and fallback forms)
                existing_files_records = db.session.query(File.id, File.file_path).all()
                existing_paths = {row[1]: row[0] for row in existing_files_records}
                
                scanned_count = 0
                added_count = 0
                found_relative_paths = set()

                # 2. Walk directory
                for file_entry in pdf_root.rglob('*.pdf'):
                    try:
                        rel_path = file_entry.relative_to(pdf_root).as_posix()
                    except ValueError:
                        continue

                    found_relative_paths.add(rel_path)
                    scanned_count += 1

                    with cls._lock:
                        cls._status["total_scanned"] = scanned_count
                        cls._status["current_file"] = file_entry.name

                    # Check if already registered
                    if rel_path in existing_paths:
                        continue

                    # Extract metadata from filename
                    stem = file_entry.stem
                    match = re.match(r'^(.*?)(?:[\s_-]*)(\d+(?:\.\d+)?)(?:_.*)?$', stem)
                    if match:
                        title_candidate, volume_str = match.groups()
                        title = title_candidate.strip()
                        if not title or title.isdigit():
                            title = stem
                            volume = 1
                        else:
                            try:
                                volume = int(float(volume_str))
                            except ValueError:
                                volume = 1
                    else:
                        title = stem
                        volume = 1

                    title = title.strip()

                    # Find or create Book
                    book = Book.query.filter_by(title=title).first()
                    if not book:
                        book = Book(title=title, author="Unknown", category="미분류")
                        db.session.add(book)
                        db.session.flush()

                    # Optional metadata auto-enrichment on scan
                    file_author = book.author
                    file_cover = None
                    display_title = stem

                    if enrich_metadata:
                        try:
                            from services.book_enricher import enrich_book_info
                            meta = enrich_book_info(title, volume=volume, author_hint=book.author)
                            if meta:
                                if meta.get('author') and meta['author'] not in ("알 수 없음", "Unknown"):
                                    book.author = meta['author']
                                    file_author = meta['author']
                                if not book.cover_url and meta.get('cover_url'):
                                    book.cover_url = meta['cover_url']
                                book.isbn_13 = meta.get('isbn') or book.isbn_13
                                book.source_category = meta.get('source_category') or book.source_category
                                book.category = meta.get('category') or book.category
                                book.metadata_source = meta.get('source') or book.metadata_source
                                file_cover = meta.get('cover_url')
                                display_title = meta.get('title') or stem
                        except Exception as enrich_err:
                            logger.debug(f"Scan enrichment error for {stem}: {enrich_err}")

                    new_file = File(
                        book_id=book.id,
                        file_path=rel_path,
                        volume_number=volume,
                        total_pages=0,
                        title=display_title,
                        author=file_author,
                        cover_url=file_cover
                    )
                    db.session.add(new_file)
                    if not book.category:
                        book.category = "미분류"
                    existing_paths[rel_path] = True
                    added_count += 1

                    with cls._lock:
                        cls._status["new_added"] = added_count

                    # Commit in batches to prevent transaction bloating
                    if added_count % batch_size == 0:
                        db.session.commit()

                # Commit remainder
                db.session.commit()

                # 3. Clean up missing/deleted files if requested
                removed_count = 0
                if clean_missing:
                    for db_path, file_id in existing_paths.items():
                        if db_path not in found_relative_paths:
                            file_to_del = db.session.get(File, file_id)
                            if file_to_del:
                                db.session.delete(file_to_del)
                                removed_count += 1
                    if removed_count > 0:
                        db.session.commit()
                        logger.info(f"Cleaned up {removed_count} deleted files from DB.")

                # 4. Efficient batch update of total_volumes for all books using single GROUP BY query
                volume_counts = db.session.query(
                    File.book_id,
                    func.count(File.id).label('file_count')
                ).group_by(File.book_id).all()

                counts_by_book = dict(volume_counts)
                all_books = Book.query.all()
                for b in all_books:
                    actual_count = counts_by_book.get(b.id, 0)
                    if b.total_volumes != actual_count:
                        b.total_volumes = actual_count
                
                db.session.commit()

                duration = round(time.time() - start_t, 1)
                logger.info(f"Scan complete: {scanned_count} scanned, {added_count} added, {removed_count} cleaned in {duration}s")

                with cls._lock:
                    cls._is_running = False
                    cls._status["state"] = "completed"
                    cls._status["duration_seconds"] = duration
                    cls._status["message"] = f"스캔 완료: {added_count}권 신규 등록 ({duration}초 소요)"
                    cls._status["removed_count"] = removed_count

            except Exception as e:
                db.session.rollback()
                duration = round(time.time() - start_t, 1)
                logger.error(f"Error during background scan: {e}", exc_info=True)
                with cls._lock:
                    cls._is_running = False
                    cls._status["state"] = "error"
                    cls._status["duration_seconds"] = duration
                    cls._status["message"] = f"스캔 중 오류 발생: {str(e)}"
