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

## In progress

## Next

## Notes
- Target Environment: Synology DS220j NAS (Realtek RTD1296 4-core, 512MB RAM) + Local PC development.
- Zero extra heavy dependencies (e.g. no Redis/Celery) to respect 512MB RAM constraints.
- Existing database (`instance/library.db`) with 29 files, 18 books, and reading states successfully migrated and preserved with zero data loss.
- Evaluator subagent verified and passed all 7 acceptance criteria.

