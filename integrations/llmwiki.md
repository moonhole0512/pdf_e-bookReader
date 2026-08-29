# LLM Wiki Integration

Use this integration when a task involves conversation archives, research notes, domain knowledge, decisions, or reusable troubleshooting.

## Source of truth

- If the target project provides `.agents/skills/karpathy-llm-wiki/SKILL.md`, follow that skill for ingest, query, archive, and lint behavior.
- Resolve the Wiki root from project configuration or an environment variable such as `LLMWIKI_ROOT`; do not assume a fixed machine path.
- Treat an upstream conversation converter as a read-only normalizer/archive. Never write through a junction or symlink into its output directory.

## Routing

1. Preserve the normalized session in the Raw/archive layer with its stable session ID.
2. Remove only structural noise from the derived transcript; keep the original source available for evidence.
3. Triage the source as `New`, `Update`, `Disputed`, `No material`, or `Archive only`.
4. Compile durable knowledge into topic-based Wiki articles. Do not add every transcript to `wiki/index.md`.
5. Keep Wiki articles grounded in their Raw sources and update `wiki/index.md` and `wiki/log.md` when an article changes.
6. Queries are read-only unless the user explicitly asks to archive the answer.

For Wiki changes, use `agents/wiki-evaluator.md` rather than a screenshot-focused application evaluator.
