# Skill Specification: Autonomous Agentic Loops

## 1. Objective
Evolve Milo from single-turn tool calls into an autonomous, multi-step execution engine capable of planning, executing tools in a ReAct (Reason + Act) loop, recovering from errors, and yielding structured state updates for future API/mobile integration.

---

## 2. Architecture & Design Principles
* **Event-Driven Yielding:** The loop core is a generator yielding structured event dictionaries rather than hardcoding terminal `print()` statements. This decouples logic from presentation.
* **Bounded Execution:** Every loop has a hard stop limit (`max_iterations = 6`) to prevent runaway API loops and token bloat.
* **Safety First:** `RISK_HIGH` tools must explicitly pause execution and prompt for user confirmation before proceeding.

---

## 3. Core Event Schema
During execution, the loop yields events in the following format:
- `tool_call`: Emits the tool name and arguments being executed.
- `tool_result`: Returns the output or traceback from the tool execution.
- `final_answer`: The terminal response text generated once the task is complete.
- `error`: Captures unhandled exceptions or iteration limit warnings.

---

## 4. Proposed Directory Structure
```text
milo/
├── agent.py         # Core ReAct loop & event stream generator
├── registry.py      # Tool loading and risk decorators
└── tools/           # Existing tool modules (system, git, rag, etc.)
docs/
└── agentic_loops.md  # This design specification