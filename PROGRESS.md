## Done
- [x] [Implementation] Codebase inspection & structural issue diagnosis
- [x] [Implementation] Created ARCHITECTURE.md & initial PROGRESS.md
- [x] [Implementation] Step 1: Database models & SQLite WAL/timeout concurrency enhancement
- [x] [Implementation] Step 2: Portable path handling & existing DB automatic migration
- [x] [Implementation] Step 3: Non-blocking background PDF scanner with progress API & N+1 count optimization
- [x] [Implementation] Step 4: Security & authorization enhancement (protected static PDFs, admin auth)
- [x] [Implementation] Step 5: Modular architecture with Flask Blueprints (auth, library, reader, admin, api)
- [x] [Implementation] Step 6: Portable Windows local test runner (run.bat) & test suite (_testcode/specs/)
- [x] [Implementation] Step 7: Live verification, Evaluator subagent PASS & end-to-end testing
- [x] [Implementation] Step 8: High-precision online book metadata engine (`services/book_enricher.py`, Aladin + Google Books, 500px high-res covers, strict volume collision prevention)
- [x] [Implementation] Step 9: Non-blocking batch enrichment API (`/api/admin/enrich`) & UI ("정보 자동 검색" button with live status polling)
- [x] [Implementation] Step 10: Background PDF scanner integration (`enrich_metadata=True`) & unit/integration test suite (`test_enricher.py`)
- [x] [Implementation] Step 11: 100% verified on live database (18 books, 29 files all matched with zero false positives) and Evaluator subagent PASS
- [x] [Debugging] Step 12: SpineShelf elimination (0 remaining in DB, front 500px covers enforced), novel vs comic disambiguation (Buriki matched), canonical author accuracy (Robert Cialdini matched), and Apple-like modal UI/UX overhaul with multi-source candidate selection & fixed aspect ratio (Evaluator subagent PASS)

- [x] [Implementation] Step 13: Phase 1 - Clean Header (Apple-style settings modal hub), Mobile 2-column grid (< 600px) & iOS Segmented Control (Reading / Unread / Completed / All)
- [x] [Implementation] Step 14: Phase 2 - Frictionless Series Continuation (Hero continue card with next volume jump, volume modal intelligent focus & reader end-screen completion sheet)
- [x] [Implementation] Step 15: Phase 3 - Psychological Motivation & Discovery (Unread discovery banner, "오늘 뭐 읽지?" shuffle picker modal & gold completion badges)
- [x] [Implementation] Step 16: Phase 4 - Multi-Device Mastery (Mobile floating bottom tab bar with iOS safe-area support, tablet responsive tuning & desktop keyboard shortcuts)

## In progress

## Next

## Notes
- Target Environment: Synology DS220j NAS (Realtek RTD1296 4-core, 512MB RAM) + Local PC development.
- Zero extra heavy dependencies (e.g. no Redis/Celery/Selenium) to respect 512MB RAM constraints. Lightweight `requests` + regex based. Pure CSS3 + Vanilla JS.
- Existing database (`instance/library.db`) with 29 files, 18 books, and reading states 100% preserved and enriched.
- 17/17 automated tests passed in `_testcode/specs/` (including `test_ui_ux.py`).
- Evaluator subagent verified all Phase 1-4 UI/UX and Reading Motivation criteria and confirmed PASS.



