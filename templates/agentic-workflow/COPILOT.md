# COPILOT.md

## Orchestration defaults (GitHub Copilot CLI)

* Run independent work in parallel lanes/sessions; keep one objective per lane.
* If work has 3+ steps, start in plan mode before implementation.
* Use subagents/tools for exploration and batch verification to keep context clean.

## 3-phase contract (required)

1. **Plan** in `tasks/todo.md` with scope boundaries and acceptance checks.
2. **Execute** with minimal, convention-aligned code changes.
3. **Review** with test evidence and lessons recorded in `tasks/lessons.md`.

## Completion gate

Do not mark done until:

* targeted checks pass,
* merge-gate checks pass (repo-defined),
* and behavior is verified end-to-end.

## Engineering principles

* Keep diffs surgical.
* Fix root causes, not symptoms.
* Avoid silent failures and broad exception swallowing.

## Self-improvement loop

After each fix or rollback, append a reusable rule to `tasks/lessons.md`.
