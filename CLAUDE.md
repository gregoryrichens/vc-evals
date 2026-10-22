# CLAUDE.md — vc-evals

## What this is
Checks for a VC fund's LLM output: the pre-call brief (an Attio note titled "Founder Call Brief — <date>") and the AI IC member's votes. Read docs/build-guide.md before large changes.

`score`: score chosen briefs from Attio (`--note` or `--deal`), or one brief from standard input (`--stdin`).

`ic`: check one AI IC member vote from standard input (`--stdin`): format, values and the seven gates.

## Words
The pre-call note is a "brief". Never call it a memo.

## Hard rules
- NEVER commit fund data: company names, deal IDs, brief text, votes, decks. Fixtures are invented. out/ is git-ignored.
- Attio access is READ-ONLY. Do not add write calls.
- No LLM calls in this repo. No Anthropic key. Briefs are made by the n8n workflow.
- No command may read or score every brief by default. `score` needs exactly one selector.
- NEVER call live APIs in tests. Tests use fixtures/.
- NEVER assume a minimum number of examples. Every command must run with 0 briefs. Every result shows n. Below n=5, print rows and no percentages.
- A stored brief is checked against the prompt version that was live when its note was created: the spec with the latest `go_live` at or before the note's `created_at`. There is no fallback version. If none was live, the brief is "no version live" and is not a failure. The Prompt and Model lines in a brief are the model's own claim and never choose the spec.
- Headings, Inputs lines and limits come from prompts/<version>.spec.toml. Do not hard-code them.
- Do not change files in docs/ or prompts/ unless asked.
- Keep it simple. Ask before adding a dependency.
- Do not invent API details. Check https://docs.attio.com. If unsure, say "verify against <url>".

## Stack
Python 3.12, uv, httpx, pydantic, typer, textstat, pysbd, pytest, ruff.

## Commands
- Install: `uv sync`
- Lint and test: `uv run ruff check . && uv run pytest -q`
- Score stored briefs: `uv run vc-evals score --deal <id> --limit 1`
- Check an AI IC member vote: `uv run vc-evals ic --stdin < vote.json`

## When stuck
Write the question in docs/QUESTIONS.md and stop.
