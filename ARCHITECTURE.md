# Architecture Map (CODE_MAP)

## Overview
Lightweight, mobile-friendly E-Book & Comic Reader web application built with Flask, SQLAlchemy, and pdf.js, tailored for low-resource environments such as Synology NAS DS220j (512MB RAM) and local Windows development.

## Core Modules & Directory Layout
```text
e-book_reader/
├── app.py                  # Application entrypoint & Flask app factory
├── config.py               # Environment configuration (DB, PDF root, Secret key)
├── models.py               # SQLAlchemy Database models (User, Book, File, ReadingState)
├── gunicorn_config.py      # Production WSGI config for low-spec NAS (single worker, optimized timeout)
├── Dockerfile              # Containerization recipe for NAS deployment
├── run.bat                 # Windows one-click runner for local testing
├── blueprints/             # Modular route blueprints (Separation of Concerns)
│   ├── auth.py             # User login, logout, session management
│   ├── library.py          # Bookshelf UI, search, pagination, grouping
│   ├── reader.py           # Web PDF reader viewer & reading progress API
│   ├── admin.py            # PDF library scanner, metadata editor, background scan status
│   └── api.py              # External integrations (Google Books metadata lookup)
├── services/               # Core business services
│   ├── scanner.py          # Non-blocking background PDF file scanner & sync
│   ├── book_service.py     # Book grouping, optimized queries, metadata fetcher
│   └── categories.py       # Compact app-owned category normalization
├── templates/              # Jinja2 HTML templates
│   ├── index.html          # Main library bookshelf view
│   ├── reader.html         # pdf.js reader view
│   ├── login.html          # Login view
│   └── _book_list.html     # Paginated book list partial
├── static/                 # Static assets
│   ├── css/style.css       # Responsive styling (Dark mode, Apple-like simplicity)
│   └── js/
│       ├── library.js      # Main library & ISBN lookup client logic
│       └── reader.js       # pdf.js viewer controls & auto-save reading position
└── _testcode/              # Isolated sandbox for tests & debug (Rule compliant)
    ├── specs/              # Permanent automated unit & integration tests
    └── debug/              # Debug logs & snapshots
```

## Data Flow & Invariants
1. **Portable Paths**: Database stores file paths relative to `PDF_ROOT_PATH` using POSIX separators (`/`). File resolution joins `PDF_ROOT_PATH` + relative path at runtime to ensure NAS & PC portability.
2. **Reading State**: Reading progress is uniquely keyed by `(user_id, file_id)`, allowing multiple users to read the same file independently.
3. **Discovery Metadata**: `Book` stores ISBN-13, a provider category path, one compact app-owned filter category, and metadata source. Provider paths remain available for traceability, while the UI normalizes them into a small vocabulary (`소설`, `라이트 노벨`, `만화`, `비문학`, `실용`, `미분류`). Mixed JSON-LD tag lists are never used. Books with no provider category remain `미분류` so none disappear from discovery.
4. **Concurrency**: SQLite runs with `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` to prevent `database is locked` errors during concurrent reads/writes.
5. **Non-blocking Operations**: Large library scanning runs in a detached background thread with atomic batch commits and status reporting.
6. **Metadata Refresh Safety**: New PDFs receive metadata during PDF scanning. Existing-library maintenance defaults to filling missing fields only; an explicitly selected full refresh is required before existing metadata may be replaced.
