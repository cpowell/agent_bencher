Use context-mode tools when inspecting large codebases or processing large outputs.

Rules:
- Prefer `ctx_execute` over repeated `Read`/`Grep` when you need counts, summaries, filtering, or aggregation.
- Prefer `ctx_index` + `ctx_search` for docs or large markdown/text corpora you may query repeatedly.
- Prefer `ctx_fetch_and_index` for external docs/pages, then `ctx_search`.
  - **Never use `WebFetch`** — it redirects to `ctx_fetch_and_index`. Always call `ctx_fetch_and_index` directly for web content.
- Use plain `Read` only for short files or final spot checks.

When asked to write a commit message, invoke the conventional-commit skill first.
Always display commit messages in a fenced markdown code block.
