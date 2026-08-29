import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from models import db, Book, File, ReadingState

def resolve_pdf_path(pdf_root: str, file_path_str: str) -> Optional[Path]:
    """
    Safely resolves a DB file_path to an absolute Path.
    Handles both modern POSIX relative paths and legacy absolute paths gracefully.
    """
    if not pdf_root or not file_path_str:
        return None

    root = Path(pdf_root).resolve()

    # 1. Check if path is absolute
    p = Path(file_path_str)
    if p.is_absolute() and p.exists():
        return p

    # 2. Treat as relative to pdf_root
    full_path = (root / file_path_str).resolve()
    if full_path.exists():
        return full_path

    # 3. Fallback: match by filename inside pdf_root (for cross-environment migrations)
    filename = p.name
    candidate = (root / filename).resolve()
    if candidate.exists():
        return candidate

    return full_path # Return resolved target even if missing for error reporting

def get_recommended_books(limit: int = 5) -> List[Book]:
    """
    Fetches random books efficiently using SQLite RANDOM() without loading all IDs into memory.
    """
    return Book.query.order_by(func.random()).limit(limit).all()

def group_files_by_book(files: List[File], user_id: int) -> List[Dict[str, Any]]:
    """
    Groups a list of File objects by Book with eager loading.
    Serializes files with reading progress for UI cards and modal drawers.
    """
    if not files:
        return []

    file_ids = [f.id for f in files]

    # Pre-fetch all relevant reading states in a single query
    reading_states = db.session.query(ReadingState).filter(
        ReadingState.user_id == user_id,
        ReadingState.file_id.in_(file_ids)
    ).all()
    states_by_file = {state.file_id: state for state in reading_states}

    groups = {}
    for f in files:
        if f.book_id not in groups:
            groups[f.book_id] = []
        groups[f.book_id].append(f)

    grouped_list = []
    for book_id, file_list in groups.items():
        file_list.sort(key=lambda item: item.volume_number)
        cover_file = next((f for f in file_list if f.volume_number == 1), file_list[0])

        serializable_files = []
        has_reading = False
        all_completed = True
        latest_file = None
        latest_time = None

        for f in file_list:
            reading_state = states_by_file.get(f.id)
            current_page = reading_state.current_page if reading_state else 0
            is_completed = (f.total_pages > 0 and current_page >= f.total_pages * 0.95)

            if reading_state and reading_state.last_read_at:
                if not latest_time or reading_state.last_read_at > latest_time:
                    latest_time = reading_state.last_read_at
                    latest_file = f

            if current_page > 0 and not is_completed:
                has_reading = True
                all_completed = False
            elif current_page == 0:
                all_completed = False

            serializable_files.append({
                "id": f.id,
                "title": f.title or (f.book.title if f.book else "Untitled"),
                "author": f.author or (f.book.author if f.book else ""),
                "volume_number": f.volume_number,
                "cover_url": f.cover_url or (f.book.cover_url if f.book else None),
                "current_page": current_page,
                "total_pages": f.total_pages,
                "is_completed": is_completed
            })

        if all_completed and len(file_list) > 0:
            status = 'completed'
        elif has_reading or (latest_file and not all_completed):
            status = 'reading'
        else:
            status = 'unread'

        main_book = file_list[0].book
        grouped_list.append({
            "book": main_book,
            "files": serializable_files,
            "volume_count": len(file_list),
            "cover_file": cover_file,
            "status": status,
            "latest_file": latest_file,
            "last_read_at": latest_time
        })

    grouped_list.sort(key=lambda g: (g['book'].title if g['book'] else ""))
    return grouped_list
