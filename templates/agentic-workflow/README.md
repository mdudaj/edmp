# Portable agentic workflow template

This template packages a parallel-agent workflow that can be copied into any repository and used with both Claude Code and GitHub Copilot CLI.

## What it includes

* `CLAUDE.md`: orchestration and quality rules for Claude Code sessions.
* `COPILOT.md`: equivalent rules for GitHub Copilot CLI sessions.
* `.github/copilot-instructions.md`: repository-level Copilot coding guardrails.
* `tasks/todo.md`: 3-phase execution tracker (Plan, Execute, Review).
* `tasks/lessons.md`: persistent lessons learned and anti-repeat rules.

## Bootstrap into a repo

From this repository root:

```bash
.github/scripts/scaffold_agentic_workflow.sh /path/to/target/repo
```

By default, existing files are preserved. Use `--force` to overwrite template-managed files.
Use `--dry-run` to preview files that would be written without changing the target repo.

## Core operating model

1. Run multiple independent sessions in parallel.
2. Require planning for work with 3+ steps.
3. Execute in three phases: plan, execute, review.
4. Verify before completion (targeted checks, then merge-gate checks).
5. Record corrections in `tasks/lessons.md` so future sessions avoid repeats.
