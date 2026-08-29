# Gemini (Antigravity) Advanced Agent Harness

This repository is a heavily upgraded adaptation of the Anthropic `cwc-long-running-agents` harness, tailored and expanded specifically for Google's Gemini (Antigravity) agent.

It transforms the AI from a simple code generator into a **fully autonomous, user-centric Senior Developer & Product Manager** by enforcing strict rules on UI/UX philosophy, code organization, automated evaluation, and project memory.

## Core Features & Philosophy

| Feature | Description |
|---|---|
| **Apple-like UI/UX Philosophy** | The agent is instructed to prioritize "Radical Simplicity" and "Don't Make Me Think". It will automatically hide complex configurations and implement frictionless interactions (like auto-complete) by default. |
| **Automatic Self-Evaluation** | Before marking any task as complete, the agent automatically spawns a separate `evaluator` subagent to rigorously verify the code and visual evidence. |
| **Product Strategist Subagent** | Includes a dedicated `/기획자` (Product Strategist) subagent that analyzes the project and proposes high-ROI "Wow" features and UX improvements. |
| **Architecture Map Maintenance** | Prevents AI hallucination and repetitive searches by forcing the agent to maintain a high-level `ARCHITECTURE.md` (Code Map). |
| **Test Code Isolation** | Keeps the root and `src/` directories pristine. One-off scripts go to `_testcode/temp/` (ignored by git), and formal tests go to `_testcode/specs/`. |
| **Python Portable Environment** | Enforces `.venv` usage and automatically generates a `run.bat` file for one-click execution without terminal hassle. The AI handles dependency updates silently. |
| **Verification Gate** | The agent is forbidden from passing tests without explicitly using the `view_file` tool to visually confirm screenshots or console logs. |

## Repository Structure

```text
gemini-long-running-agents/
├── AGENTS.md                  # General development rules
├── integrations/              # Optional LLM Wiki/OpenWiki routing rules
├── agents/
│   ├── evaluator.md           # Application reviewer
│   ├── wiki-evaluator.md      # LLM Wiki reviewer
│   ├── debugger.md            # Debugging specialist
│   ├── rd-specialist.md       # Research specialist
│   └── product-strategist.md  # UX/Product planning specialist
├── ARCHITECTURE.md
└── PROGRESS.md
```

## How to Use

1. **Setup:** Copy the base `AGENTS.md`, `agents/`, and any needed `integrations/` files into the root directory of your target project. LLM Wiki and OpenWiki are optional.
2. **Start the Loop:** Open Antigravity (Gemini) in your project and simply type:
   > "현재 프로젝트 코드를 검토해줘" (Review the current project code)
   
   The agent will immediately read `AGENTS.md`, establish `PROGRESS.md` and `ARCHITECTURE.md`, and await your instructions.
3. **Autonomous Execution:** Use the host agent's supported goal or task mechanism to start the build -> test -> evaluate loop. Do not assume a `/goal` command exists in every environment.
4. **Strategic Planning:** Whenever a major feature is done, the agent will recommend a strategic review. Simply type `/기획자` to have the Product Strategist subagent analyze your app and propose killer features.
