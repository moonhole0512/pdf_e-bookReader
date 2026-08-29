# Long-running conventions for this project

## UI/UX Design Philosophy (Apple-like Simplicity)
When designing interfaces (both graphical and command-line), you MUST adhere to the following user-centric philosophy:
1. **Radical Simplicity (Less is More):** Eliminate unnecessary options. Do not overwhelm the user with settings. The interface should be immediately intuitive ("Don't make me think").
2. **Automate the Complex:** Hide complexity under the hood. Automatically determine the optimal defaults or configurations without asking the user.
3. **Frictionless Interaction:** Anticipate user needs to reduce typing and clicking. Implement modern UX patterns like auto-complete, smart dropdowns, and input auto-formatting wherever applicable.
4. **Guided Choices:** If a choice must be made, present only the most essential options clearly, rather than exposing the raw underlying configuration.

## Always start here
Before doing anything else, read `PROGRESS.md` and `ARCHITECTURE.md` (or `CODE_MAP.md`). `PROGRESS.md` is your handoff note from the previous session. If it doesn't exist yet, create it now with four sections (`## Done`, `## In progress`, `## Next`, `## Notes`) and leave them empty. Then run `git log --oneline -10` to see what was just committed, and run the project's smoke test (or `npm run build` / `npm test`) once so you know you're starting from a working tree, not a broken handoff.

## Architecture Map Maintenance
Maintain an `ARCHITECTURE.md` (or `CODE_MAP.md`) file in the project root. When you start a session, read it alongside `PROGRESS.md` to quickly understand the project's layout without searching blindly. 
- Keep it high-level (e.g., directory roles, core module locations, common utilities, and data flow).
- Do not list individual function details, parameters, or excessively granular logic to prevent document drift.
- Only update this file when you create a new core module, significantly change the directory structure, or add a major shared utility.

## One feature at a time
Work on exactly one item from `PROGRESS.md` per session. Finish it (tests passing, visual verification) before starting another. If the user gives you a new task mid-session, add it to `PROGRESS.md` and finish the current item first.

## Proof before passing (The Verification Gate)
A test is only "passing" after you have:
1. Run it against the live app
2. Opened the resulting screenshot or console log using the `view_file` tool.
3. Confirmed it shows what it should.

**CRITICAL RULE**: Do not write to or mark any item in `test-results.json` or `PROGRESS.md` as complete unless you have explicitly viewed the evidence file in the same turn or session.

## Automatic Evaluation (Self-Verification)
Before marking any feature as `Done` in `PROGRESS.md`, you **MUST** autonomously invoke the evaluator subagent to verify your work:
1. Use the available subagent mechanism with the prompt appropriate to the task: `agents/evaluator.md` for application work, or `agents/wiki-evaluator.md` for LLM Wiki work.
2. Pass the specific acceptance criteria and instructions to the subagent.
3. Wait for the subagent's response. 
4. If it returns `NEEDS_WORK`, fix the listed issues. You may only proceed to the next feature if the evaluator returns `PASS`.

## Optional Knowledge Integrations

LLM Wiki and OpenWiki are complementary integrations, not mandatory dependencies. Do not assume that either one exists in every target project.

### 1. Layer responsibilities
- **LLM Wiki** stores conversation archives, research notes, domain knowledge, decisions, and reusable troubleshooting.
- **OpenWiki** stores codebase architecture, API contracts, invariants, and line-level `repo://` claims.
- Use only the integration relevant to the current task. If both kinds of knowledge are produced, update each layer separately.
- Load `integrations/llmwiki.md` or `integrations/openwiki.md` when present. Prefer project-local instructions over hard-coded machine paths.
- If `.agents/skills/karpathy-llm-wiki/SKILL.md` exists, use it as the source of truth for Wiki ingestion, query, and lint behavior.

### 2. Activation and staleness audit
Before starting planning or implementation on a non-trivial feature, debugging a complex error, or integrating third-party technologies (e.g., AI models, APIs, tools):
1. Activate LLM Wiki only when the task involves archives, research, domain knowledge, decisions, or reusable troubleshooting, and only when the Wiki is available.
2. Activate OpenWiki only when the project has `openwiki/`, `.claims/`, or an explicitly configured equivalent.
3. If an integration, command, or evidence tool is unavailable, use an available equivalent and report the limitation. Never fabricate a successful update.
4. For fast-changing knowledge, inspect article metadata and refresh stale sources when the integration supports it.

### 3. Update behavior
During CLI usage or development sessions:
1. Keep normalized conversation sessions in the Raw/archive layer. Triage each source as `New`, `Update`, `Disputed`, `No material`, or `Archive only` before compiling durable knowledge into topic-based Wiki pages.
2. Use OpenWiki claims only for code facts and only when the claim store is configured. Do not run `openwiki --update` or edit `.claims/` when those resources are absent.
3. Preserve stable session IDs as metadata even when human-readable titles are generated. Do not place every transcript in `wiki/index.md`.


## Core Working Modes & Autonomous Escalation
Before acting on a task, you MUST autonomously classify it into one of three modes. Do not ask the user to choose the mode unless the request is genuinely ambiguous. Start with the lightest sufficient mode to prevent over-engineering.

1. **Implementation Mode:** For straightforward coding, feature additions, or tasks where conventional techniques are sufficient. Implement directly and preserve the existing structure.
2. **Debugging Mode:** For fixing broken behavior. If a simple implementation fails twice, automatically escalate to Debugging Mode.
3. **Research Mode (R&D):** For novel, complex problems (e.g., cutting-edge algorithms, unexplored technology) or when debugging reveals a fundamental structural limitation.

**The R&D Loop (Research Mode):**
If a task is classified as `[Research]`, you must STOP conventional coding and strictly follow this loop:
1. **State of the Art (SotA) Review:** Review existing open-source solutions, technical limitations, and available techniques.
2. **Hypothesis & PoC:** If existing tools fall short, formulate a novel hypothesis. Write a minimal Proof of Concept (PoC) script in `_testcode/temp/` to test it. Do not touch the main application codebase yet.
3. **Measurable Evaluation:** Test the PoC and gather objective success metrics.
4. **Implementation Plan:** Once the PoC is proven, write a concrete integration plan as a Markdown artifact and seek user approval before integrating it into production.
*Note: For heavy, open-ended research tasks, you MUST delegate the research and PoC creation to the R&D Specialist Subagent by invoking the prompt in `agents/rd-specialist.md` to prevent context pollution.*

## Keep `PROGRESS.md` current
After each completed item, update `PROGRESS.md`: check off what's done, add what you learned, note what's next. Future sessions read this file cold. When adding new tasks, prefix them with their classified mode tag (e.g., `[Implementation]`, `[Debugging]`, `[Research]`).

## Commit often
Whenever you complete a meaningful checkpoint, use `run_command` to `git add` new files and commit with a descriptive message. Always commit your work before stopping or ending your turn.

## Operator Steering
If you notice a file named `STEER.md` in the project root, read it immediately. Pause what you were about to do, incorporate the guidance inside `STEER.md`, clear the file's contents, and then continue toward the feature goal.

## Proactive Recommendations & Custom Commands
When you finish a major feature or empty the "Next" queue in `PROGRESS.md`, you should proactively suggest strategic review.
Output a message exactly like this to the user:
> "✅ 작업을 완료했습니다. 다음 단계로 넘어가기 전 기획 점검(Product Strategy Review)을 수행하시길 추천합니다. 이를 원하시면 `/기획자` 라고 입력해 주세요."

If the user types `/기획자` (or asks for the product strategist), you **MUST** immediately invoke the subagent using the prompt in `agents/product-strategist.md` without asking for further clarification.

## Code Organization & Sandbox (Test Code Isolation)
All test and verification code must be isolated from the `src/` directory to keep the production codebase clean. Use the top-level `_testcode/` directory for this purpose.
1. **One-off Scratch Scripts:** Any temporary code written for quick API checks, logic verification, or debugging MUST be placed in `_testcode/temp/`. This folder should be added to `.gitignore`.
2. **Formal Tests (Specs):** Permanent unit and integration tests (e.g., `*.spec.ts`, `test_*.py`) MUST be placed in `_testcode/specs/`. Mirror the directory structure of `src/` inside `specs/`. (e.g., tests for `src/auth/login.js` go to `_testcode/specs/auth/login.spec.js`).
*Exception: If the framework (e.g., Next.js) strictly enforces test file colocation, follow the framework's convention over this rule.*

## Autonomous Debugging & Logging
1. **Centralized Debugging Directory (`_testcode/debug/`):** All debugging files generated during application execution or testing MUST be placed inside the `_testcode/debug/` directory to keep the project structure clean.
2. **Dual-Level Logging & Overwrite:** Console output should be kept concise (INFO level) for the user to monitor progress. Detailed debug data (tracebacks, API responses, state variables) MUST be redirected to `_testcode/debug/debug.log`. To maintain efficiency in the test environment, overwrite this log file on each run rather than appending to it.
3. **No Copy-Paste Rule (Proactive Log Exploration):** When an application crash occurs OR when the user reports a functional bug (silent failure), NEVER ask the user to copy and paste error messages or logs. Your first reflex MUST be to autonomously read the recent entries in `_testcode/debug/debug.log` using file-reading tools to investigate the transaction.
4. **Contextual State Snapshot (`crash_dump.md`):** If a complex error occurs requiring deep analysis, do not blindly dump everything. Gather only the *relevant context* (e.g., specific problematic variables, recent API request/response bodies, or minimal targeted DB query results) along with the last 50 lines of logs, and write them to `_testcode/debug/crash_dump.md` before switching to Debugging Mode.
5. **Debugger Subagent:** For stubborn bugs that persist after initial attempts, you MUST delegate the analysis to the Debugger Subagent by passing the path to the crash dump and logs. (Use the prompt in `agents/debugger.md`).
6. **Troubleshooting & Debugging Knowledge Ingestion:** When a non-trivial bug, crash, or implementation failure is resolved, the agent MUST record a concise "Troubleshooting & Root Cause Analysis" section in the project's Wiki document (`wiki/`) detailing the symptoms, root cause, applied fix, line-level code references (`repo://path#L10-L30`), and prevention guidelines for future sessions.


## Python Portable Environment
When working on Python projects, you MUST strictly adhere to the following portable environment rules:
1. **Enforce venv:** Do not pollute the global Python environment. Always create and use a virtual environment named `.venv` in the project root.
2. **One-Click Execution (`run.bat`):** Always provide a `run.bat` file in the project root so the user can run the application with a single click without manually opening a terminal. 
   - The `run.bat` file MUST contain conditional logic to check if the `.venv` folder exists.
   - If `.venv` does NOT exist, the script should automatically create it and run `pip install -r requirements.txt`.
   - If `.venv` DOES exist, the script should skip installation, activate the virtual environment, and run the main application immediately.
3. **Dependency Maintenance:** If you (the AI agent) add or modify dependencies in `requirements.txt` during your work, you MUST proactively run the installation command (e.g. `pip install`) via terminal tools yourself, so the environment is ready before the user clicks `run.bat`.

## Absolute Portability (Cache Isolation)
Never pollute the user's global system directory (e.g., `~/.cache` or `%USERPROFILE%\.cache`). If your code requires downloading models, weights, datasets, or any large caching mechanisms, you MUST configure it to use a local directory within the project root (e.g., `./.cache` or `./weights`) and add it to `.gitignore`. Ensure the environment remains strictly portable.
