# Build Guide (v6)

Date: 2026-10-14. Status: v6. It replaces v5. v6 changes what the harness is: it scores chosen briefs. It no longer reads every brief in Attio (see section 2b).

Step 0 copies this file into the repo as `docs/build-guide.md`. Section 9 is the first Claude Code prompt.

---

## 1. Words

- **Brief:** the Attio note that the n8n workflow makes before a founder call. Its title is "Founder Call Brief — YYYY-MM-DD". Use only this word for it.
- **IC memo:** a different document. It is not in scope.
- **Harness:** the `vc-evals` repo. It scores LLM output. It makes no LLM calls itself.
- **Spec file:** a small file that lists the headings, Inputs lines and limits that one prompt version must produce.

---

## 2. Goal

Do one full forward-deployed loop on the fund's existing Claude setup.

**Rule: practical minimum.** No app, API server, database, MCP server, or hosting. The fund's stack is the platform.

---

## 2a. How checks are chosen

v4 picked the brief and the AI IC member because they were easy to measure. It chose brief checks from what code can count. It dropped deal intake without a decision. v5 corrected this.

**For each workflow, ask four questions first. The checks come from the answers.**

1. Who uses the output, and for what decision?
2. What does a bad output look like, and what does it cost?
3. How is a bad output noticed today?
4. What would be done differently if it were noticed sooner?

**Brief (answered 8 Oct):**
1. GPs and investors, to prepare for the founder call.
2. Bad = too technical to skim, padded with irrelevant points, misses what matters. Cost: the GP ignores it, wastes prep time, has a weaker call, and stops trusting the automation. Wrong or unsupported claims were not named as a main problem.
3. Greg reads briefs himself. Otherwise it is not noticed.
4. Fix the prompt. So the harness is a prompt-tuning loop: score the briefs that a candidate prompt makes, then change the prompt.

**AI IC member (decision 21 Oct, Greg):** there are too few votes to compare against a baseline or to show a trend in ratings. The only eval built now checks each vote the project produces: the Step 8 format, a value in every field, and a verdict that the integrity checks and gates in the project's instructions allow. Step 5 describes it. The four questions above are still to be answered for this workflow.

**Still to ask:** deal intake, votes, and the four questions for the AI IC member.

**Three layers of checks.**

| Layer | Checks | Applies to | Status |
|---|---|---|---|
| 1. Template conformance | Required headings present, non-empty. Required Inputs lines present. Limits kept (word count, no tables). Values in the allowed set (verdict Yes/No/Conditional, conviction 1–3). | Every workflow output | Build now |
| 2. Quality proxies | Word count, words per section, sentence length, readability score, jargon-list count, bullets per section against a cap, near-duplicate points. | Brief first | Built, reported only (section 2c). Thresholds are set later by calibrating on briefs Greg rates good and bad, not guessed. |
| 3. LLM judge | Relevance and coverage (are these the right points, are the risks and founder questions there). | Brief first | Later. Not built in v6. |

Layers 1 and 2 are proxies. They show shape, not whether the points are the right ones. The README must say so.

**Layer 1 per workflow.** Each output has one spec file in `prompts/`, so the template lives in data, not code.
- Brief: sections, Inputs lines, output limits and markers from `<version>.spec.toml`.
- AI IC member: the vote has the format of Step 8 of `prompts/ai_ic_v1.md`, every field has a value in its allowed set, and the verdict is one the seven gates allow (Step 5). The spec file is `prompts/ai_ic_v1.spec.toml`.
- Votes: proposal has vote, conviction, party and rationale, all in the allowed sets.
- Deal intake: the proposal summary is present. Fields the GP's text supplied are proposed. This needs test inputs with expected fields, not only outputs.

---

## 2b. What the harness does (v6)

An eval needs a chosen set of inputs. It must not need "every brief ever made". The `score` command scores the briefs that you name. The same checks run on a brief wherever it came from.

| | `vc-evals score` |
|---|---|
| Question | Is this brief, or this group of briefs, good? |
| Input | One of: `--note <id>`, `--deal <id>`, `--stdin` |
| Makes a brief? | No. It reads briefs that already exist in Attio, or one brief from standard input. |
| Output | Scores for the selected briefs. |
| Cost | Nearly free. It is one Attio read and string checks. |
| Use | After any brief is made. In production, the n8n workflow scores each new brief on GitHub before it writes the note (Step 4). |

**Rules**
- `score` needs exactly one selector: a note ID, a Deal ID or `--stdin`. There is no "all" default and no date or workspace-wide listing. Attio can list notes only by parent record, so the harness asks for one deal's notes at a time. `--deal` returns that deal's briefs, newest first. `--limit N` caps them (default 20).
- `score` exits with a non-zero code if any Layer 1 check fails. A CI step can use this.
- Every result shows n. Below 5, rows only, no percentages.

**Limits to state in the README**
- The web changes and the model is not deterministic, so two briefs from the same prompt differ.
- A stored brief's `Prompt:` and `Model:` lines are written by the model. Treat them as claims. They never choose the spec: the version is the one live on the note's creation date (`go_live` in each spec file).

---

## 2c. Layer 2 quality proxies

Layer 2 answers "is this brief easy to skim?", not "are these the right points?". Six measures, each in its own file in `src/vc_evals/layer2/`. They read the brief without its Inputs block and need no prompt version.

| Measure | What it shows | Built with |
|---|---|---|
| `words_per_section` | Where the words go. Padding shows up as one fat section. The total equals the Layer 1 word count. | Our code |
| `sentence_length` | Number of sentences, mean and longest. Long sentences are hard to skim. | [pySBD](https://pypi.org/project/pysbd/) finds the sentences |
| `readability` | Flesch Reading Ease and Flesch-Kincaid grade. | [textstat](https://pypi.org/project/textstat/) |
| `jargon` | Words not on the XKCD Simple Writer list ([xkcd.com/simplewriter](https://xkcd.com/simplewriter/words.js)), as a count and per 100 prose words (headings, numbers, tables and code blocks are not in that base). This stands in for "too technical". | Our code: the list in `xkcd_words.txt` plus a tokenizer |
| `bullets_per_section` | List items per section. Many bullets can mean padding. | Our code |
| `near_duplicates` | Pairs of sentences at least 80% alike. This stands in for repeated points. | Python `difflib` |

**How they run.** `vc-evals score` runs all six on every brief it scores and prints them in a second table. `vc-evals measure <name>` runs one, with the same one-selector rule. They never pass or fail a brief and never change the exit code.

**Decisions made 20 Oct.**
- Libraries: textstat and pySBD were approved. RapidFuzz was not, so near-duplicates use `difflib`. The word list is the XKCD list unedited. Nothing is added to it.
- The Munroe Jargon Profiler was reviewed. It is a Flask web app with no documented Python API, so we took its method (anything outside the 1,000 most common words is jargon) and wrote our own.
- A word capitalised somewhere other than the start of a sentence is taken as a name and skipped everywhere. An all-capitals word (FPGA) is not.
- The list is small, so common business words count as jargon. Compare rates between briefs. Do not read one rate as absolute.

**Calibration (not done).** Greg rates 2–3 briefs good and 2–3 bad. Run `score` on each. Look for the measures that separate the two groups. Only then add thresholds to the spec files and decide which, if any, count toward pass or fail. With so few rated briefs, expect to find that some measures say nothing.

**Known limits.** Readability formulas were made for prose, so bullet-heavy briefs may score oddly. The CMU pronouncing dictionary that textstat needs is kept in the repo (`src/vc_evals/layer2/nltk_data/`), so CI and tests never need the network.

---

## 3. Where each piece of data comes from

Nothing in this guide needs a minimum number of past examples. The automations are new.

| Data | Source | How the harness gets it |
|---|---|---|
| Stored briefs | Attio Notes on Deal records. The n8n workflow creates them with its API token. | Attio API, read-only. Only the notes that the selector names. It keeps those whose title starts with "Founder Call Brief". |
| A stored brief's inputs, prompt version, model | The "Inputs" section at the end of each brief. Briefs from `brief_v1` have it. Earlier briefs do not. | Parsed from the brief text. Treated as the model's own claim. The prompt version used for checking comes from the note's creation date and each spec's `go_live`, not from this section. |
| Web pages a brief used | The `Web:` URLs in the "Inputs" section | The harness fetches each URL once, to check that it loads, and keeps a copy in `out/`. |
| Deck text | **Not available to the harness.** | No check uses it. |
| AI IC member's vote | The AI IC member project. After it shows a vote, it sends the vote text and its own ratings (integrity checks, Four Forces, exit pathway) to n8n. | Standard input: `vc-evals ic --stdin`. n8n passes the vote to the GitHub job. The harness does not read Attio for this. |
| Votes in Attio | Attio `votes` object: verdict (Yes, No, Conditional), conviction ("1" to "3"), rationale, deal, voter_type (Human or AI) | Not read by the harness for now. Too few to compare. |
| What a brief must have | `prompts/<version>.spec.toml`. One per prompt version. Each has a `go_live` date. | Read from the repo. The spec used for a stored brief is the one with the latest `go_live` at or before the note's `created_at`. |
| What "good" means | One GP, in Step 1 | Not read by the harness. It guides your tuning. |
| Your section scores | You, in Step 2 | Not read by the harness. Not in the repo. |

**Brief formats.**
- `brief_v0` (older): seven headings (What it is, What the business rests on, Market, Competitors, What's actually real, Team, Worth digging into), an Inputs section, and source tags `[deck]`, `[verified: domain]`, `[recall/verified via …]`, `[not found]`, `[conflict]`, `[unverified externally]`. See `prompts/brief_v0.spec.toml`.
- `brief_v1` (current): five sections (What is it?, Founders, Market, Competitors, Follow Up), an Inputs section, at most 800 words, no tables. The only marker is `[not found]`. See `prompts/brief_v1.spec.toml`. Do not copy these lists into code.

---

## 4. Decisions (made with Greg)

1. Greg tunes the brief prompt by hand first. His scores are for him only.
2. No separate storage for stored briefs. Each brief lists its own inputs.
3. Collection starts after tuning. The tuned prompt is `brief_v1`. Which version a stored brief is checked against comes from its creation date and each spec's `go_live`. There is no default version.
4. Every result shows n. Below 5, the harness prints rows only, with no percentages.
5. Public numbers come from the harness checks, not from Greg's scores.
6. **(14 Oct)** The harness scores selected briefs. It does not sweep every brief in Attio.
7. **(17 Oct)** The n8n workflow scores each brief on GitHub before it writes the note. The note holds the brief and then the result. The harness has no way to make a brief. Greg tests by hand.

---

## 5. The plan — 12 hours, plus Steps 4 and 5, in this order

| Step | Work | Who | Hours |
|---|---|---|---|
| 0 | Set up the tools and an empty private repo | Greg | 0.5 |
| 1 | Discovery | Greg | 2.5 |
| 2 | Tune the brief prompt, add "Inputs", put it live | Greg, outside the harness | 4 |
| 3 | Harness: scoring core and `score` | Claude Code with Greg | 5 |
| 4 | Connect n8n to the GitHub scorer | Greg, in n8n | not estimated |
| 5 | Check the AI IC member's vote | Claude Code with Greg, then Greg in n8n | not estimated |
| | **Total** | | **12, plus Steps 4 and 5** |

Each step uses only things that an earlier step made.

---

## 6. Runbook

### Step 0 — Set up (0.5 h)

1. Install git, uv, and Claude Code on your computer, if they are not there.
2. Make a **private** GitHub repo named `vc-evals`. Clone it.
3. In the repo, make the folders `docs/` and `prompts/`.
4. Copy this file to `docs/build-guide.md`. Commit.
5. In Attio, make an API token for the harness with **read-only** access to records and notes. Verify the scope names at https://docs.attio.com. Do not use the n8n token.
6. Put the token in a file named `.env` in the repo: `ATTIO_API_KEY=...`. Add `.env` to `.gitignore` before you commit.

**Done when:** the repo exists, the guide is in it, and `.env` is not in git.

### Step 1 — Discovery (2.5 h)

1. Open the n8n brief workflow. Write down these facts. Steps 2, 3 and 4 use them.
   - The prompt text, and the model name.
   - How the workflow gets the deck.
   - How the workflow gets web pages. There are two cases: (a) n8n nodes fetch them before the LLM call, or (b) the model uses a web search tool during the call. Write which case is true.
   - The node that writes the Attio note.
   - Whether the workflow can run with the Attio note node off.
   - Whether the run log or the agent node output gives the number of tool calls.
2. Write `docs/systems-map.md`. One short section for each workflow (deal intake, brief, AI IC member, votes): who uses it, what starts it, inputs, outputs, where outputs go, how it fails today.
3. Ask one GP two questions about the brief: "What makes it good?" and "What makes it bad?" Write the answers in one or two sentences in the systems map.
4. Get answers to two questions and write them in the systems map:
   - May you publish aggregate numbers? Yes.
   - May the brief prompt and the systems map be public? If not, add `prompts/` or `docs/systems-map.md` to `.gitignore` now. Yes.

**Done when:** the systems map has all the facts from item 1, the GP agrees with the two sentences, and you have the two answers.

### Step 2 — Tune the brief prompt (4 h, Greg, outside the harness)

1. **First,** save the current production prompt as `prompts/brief_v0.md`. Do this before you change anything.
2. Write `prompts/brief_v0.spec.toml`: what the v0 prompt asks for (headings, source tags, Inputs lines, limits), and `go_live`, the date v0 went live. A spec with no `go_live` is never used. The harness picks a brief's spec from the date its note was created. Use a full timestamp (`2026-10-14T15:30:00-06:00`) if two versions went live on the same day.
3. Select the tuning set: the deals that already have a brief, plus a few deals you know well. Keep the list.
4. Tune. **Turn off the Attio note node while you tune,** or delete the test briefs afterward. If you do not, each test run adds a brief to a real Deal.
5. Score, change the prompt, and run again until the output is good. The method is yours.
6. Add the "Inputs" section. The `brief_v1` prompt asks the model to write it (Deck, Other Company Materials, Web, Prompt, Model). So the harness treats it as a claim: the model can list a page that it did not read, and it writes its own model name. The section has this form, as markdown with no code block:

   ```
   ## Inputs
   Deck: <file name or link, or "none">
   Other Company Materials: <file name or link, or "none">
   Web: <url>
   Web: <url>
   Prompt: brief_v1
   Model: <model name>
   ```

   If you later need the section to be trusted, have n8n add it after the model's text from the workflow's own data. That is not required in v6.
7. Save the tuned prompt as `prompts/brief_v1.md`. Write `prompts/brief_v1.spec.toml` with the sections, Inputs lines and limits that v1 asks for.
8. Turn the Attio note node on. Put the tuned prompt live. Write the go-live date in the systems map and in the spec file.

**Done when:** you say the output is good, both prompt files and both spec files are in the repo, and one new real brief in Attio ends with the "Inputs" section and `Prompt: brief_v1`.

### Step 3 — Harness: scoring core and `score` (5 h)

1. Run the prompt in section 9 in Claude Code. It adds the code to the repo that exists.
2. Run `uv run vc-evals score --deal <id> --limit 1`. It reads that deal's newest brief from Attio and prints one row of scores.
3. Add more checks. Layer 1 and Layer 2 are defined in section 2a. Calibrate the Layer 2 thresholds on 2–3 briefs Greg rates good and 2–3 rated bad before fixing them. Give Claude Code one item at a time and say "Build only this." All checks read the spec file. None hard-codes headings or limits.
   - **Template check:** every required section is present, written as a markdown heading, and not empty. Heading levels are the ones in the spec's `allowed_heading_levels`. Word count is at or under the limit, not counting Inputs. No tables. The limit and the table rule come from the spec's `[output]` section.
   - **Inputs check:** the Inputs lines that the spec requires are there, with the right values (`Prompt` equals the spec's version, each `Web` value is a URL). The lines must follow an "Inputs" heading. A brief with no Inputs heading fails this check.
   - **Link check** (`--links`, off by default because it uses the network): for each `Web:` URL, report loaded, or "could not fetch". It is not a fail. This check shows that a page exists. It does not show that the claim is true. Code cannot do that.
   - A count of `[not found]` was considered and dropped on 15 Oct. It says nothing a GP would act on.
   - **Layer 2 measures:** built, see section 2c. `score` runs all six. They are reported only, so calibrating thresholds is still to do.
4. Selectors: `--note <id>`, `--deal <id>` or `--stdin` (a brief read from standard input). Exactly one. `--limit N` caps a deal's briefs, newest first (default 20).
5. The output shows n. Below n = 5 it prints rows and no percentages. Each row shows the version that was live when the note was created. A note from before any version went live shows "no version live" and is not a failure. If a brief's own `Prompt:` line differs, the detail says so. It is not used to pick the spec.
6. The command exits non-zero when a Layer 1 check fails.

**Done when:** `vc-evals score --deal <id>` runs on a real deal's brief, and a new brief in Attio can be scored by `--deal <id> --limit 1` with no other action.

### Step 4 — Connect n8n to the GitHub scorer (Greg)

The workflow scores each brief on GitHub before it writes the note. The note holds the brief, then an "Eval result" section when the eval scored the brief. The GitHub job `.github/workflows/score-brief.yml` runs `vc-evals score --stdin` on the brief text. It sends the result to the waiting n8n run. The job does not call Attio.

The n8n run waits up to 3 minutes for the result. If GitHub fails or is slow, or the eval cannot score the brief, the note is still written with the brief alone. Nothing is added.

**Two secrets, two directions.** They are different values. Do not mix them up.

| | Shared secret | GitHub token |
|---|---|---|
| What it does | Lets n8n trust that a result came from the scorer | Lets GitHub trust that n8n may start the scorer |
| Direction | GitHub sends the result to n8n | n8n starts the job on GitHub |
| Who makes it | You, as a random string | GitHub, from your account |
| Where it is stored | Two places, the same value: the repo's Actions secret `EVAL_RESULT_WEBHOOK_TOKEN`, and the n8n credential on `Wait: Eval Result` | One place: the n8n credential on `GitHub: Score Brief` |
| Header | `X-Eval-Token` | `Authorization` |

Do items 2 to 4 in this order. Each uses what the one before made.

1. Import `n8n/pre-call-brief-v2-eval.json` into n8n as a copy. Do not turn the copy on while the production workflow is on. Both use the path `founder-call-brief`.
2. **Make the shared secret and save it in GitHub.** Run this in a terminal in the repo. It makes a random value, copies it to your clipboard, and saves it as the repo secret. The value is not printed.

   ```
   openssl rand -hex 32 | tee >(pbcopy) | gh secret set EVAL_RESULT_WEBHOOK_TOKEN --repo <owner>/<repo>
   ```

   Check with `gh secret list --repo <owner>/<repo>`. GitHub never shows the value again. If you lose the clipboard before item 3, run the command again.
3. **Give n8n the same shared secret.** In n8n, create a Header Auth credential. In the Name field put the header name `X-Eval-Token`. In the Value field paste the secret from your clipboard. Attach it to `Wait: Eval Result`. The Name field holds the header name, not the secret.
4. **Make the GitHub token and give it to n8n.**
   - On GitHub: Settings, Developer settings, Personal access tokens, Fine-grained tokens, Generate new token.
   - Resource owner: your account. Repository access: only `vc-evals`. Repository permissions: **Actions: Read and write**, and nothing else. Set an expiry. When it expires the job stops starting, and the note says that the eval did not finish. Put the date in your calendar.
   - Copy the token (`github_pat_…`). GitHub shows it once.
   - In n8n, create a second Header Auth credential. Name: `Authorization`. Value: `Bearer ` then the token (the word Bearer, one space, the token). Attach it to `GitHub: Score Brief`.
5. Check that `.github/workflows/score-brief.yml` is on `main`. The node starts the job on `main`.
6. In the `Config` node, find the `FRAMEWORK` value. Remove the code fence around its Inputs block. Then it matches `prompts/brief_v1.md`.
7. Verify these in n8n:
   - header auth on the Wait node's resume URL
   - `$execution.resumeUrl`
   - what the Wait node outputs when it times out
   - how Attio shows the fenced result in the note
8. Run the copy on one test Deal. The note must hold the brief and an "Eval result" section. Then remove the GitHub token from `GitHub: Score Brief` and run it again. The note must hold the brief alone. Then switch production to the copy.

The brief text goes to GitHub as a workflow input. It shows in the run page and logs. Keep the repo private. Set a short log retention.

**Done when:** a new real brief in Attio ends with the eval result, a brief made while the eval cannot run has no result added, and `vc-evals score --note <id>` on that note scores the brief and ignores the result.

### Step 5 — Check the AI IC member's vote (Claude Code with Greg, then Greg in n8n)

**The owner's decision (21 Oct).** There are too few votes to compare the AI with a baseline or to show a trend in its ratings. So the only eval built now checks each vote that the project produces, as it is produced. It checks format and gates. It does not compare votes with the GPs' votes.

**How it runs.**

1. The AI IC member project writes its vote and shows it to the IC. The IC sees it first.
2. Then the project calls a skill once. The call sends the vote text and the project's own ratings to an n8n webhook. The payload is JSON: `output` (the vote text exactly as shown) and `checks` (integrity checks, the four Four Forces ratings, and the exit pathway). The IC does not see `checks`.
3. n8n answers at once ("received"), so the IC waits for nothing.
4. n8n starts the GitHub job `.github/workflows/score-vote.yml`. The job runs `vc-evals ic --stdin` on the payload and sends `{exit_code, output}` back to the waiting n8n run.
5. If the exit code is not 0, n8n posts the failure to Slack. If the eval cannot start or does not finish in 3 minutes, n8n posts that to Slack. A vote that passes posts nothing.

**What is checked.**

| Check | What it tests |
|---|---|
| Format | The vote has the format of Step 8 of the project instructions: a header with five values, the labelled lines in order, VERDICT of YES, NO or CONDITIONAL, CONVICTION of 1, 2 or 3, six rationale bullets in order, at least one OBSERVED or CLAIMED tag, "no, now" or "no, ever" in a NO vote, 400 to 700 words, and no gate codes in the text. |
| Values in all fields | Every integrity check, every force and the exit pathway has a value from the allowed set. |
| Integrity checks and the seven gates | The verdict is one that the gates allow, given the project's own ratings. For example, Founders rated Weak requires NO (gate G3). Two or more forces Not visible means the verdict cannot be YES (gate G7). |

The allowed values, the format and the gate rules are in `prompts/ai_ic_v1.spec.toml`. They are not in the code.

**What is NOT checked.**
- Whether the ratings are right.
- Whether the thesis is good.
- Whether a CONDITIONAL vote has at most three conditions.
- Whether the vote agrees with the GPs. Agreement with the GPs is not the same as being right.

**The limit.** The gate check tests the vote against the project's own self-reported ratings. It catches inconsistency, for example a YES with Founders rated Weak. It does not catch a wrong rating, such as Founders rated Adequate when they are Weak.

**Output.** One row: company, prompt version, words, verdict, conviction, result, detail. The row shows `n = 1`. Exit code 0 means pass. Exit code 1 means a format, payload or gate failure, or input that is not valid JSON. If no spec was live, the row says "no version live". That is not a failure.

**Three secrets.** They are three different values. Do not mix them up.

| Secret | Direction | Stored in | Header | What it can do |
|---|---|---|---|---|
| Webhook token (new) | The project sends the vote to n8n | An n8n Header Auth credential on the webhook, and the skill file in the project | `X-Eval-Token` | Start one eval and, only if the eval fails, cause one Slack post. Anyone who can read the skill can read this token. |
| Result token (existing) | GitHub sends the result to n8n | The repo Actions secret `EVAL_RESULT_WEBHOOK_TOKEN`, and the n8n credential on `Wait: Eval Result` | `X-Eval-Token` | Lets n8n trust the result. Step 4 made it. The vote workflow reuses it. |
| GitHub token (existing) | n8n starts the job on GitHub | The n8n GitHub credential | `Authorization` | Starts jobs on `vc-evals`. Step 4 made it. The vote workflow reuses it. |

**Runbook.** Do items 1 to 7 in this order. Each uses what the one before made.

1. **Add the spec and the instructions.** Put `prompts/ai_ic_v1.md` and `prompts/ai_ic_v1.spec.toml` in the repo. Set `go_live` in the spec to the date you will switch the project to v1 (item 7). A vote is checked against the spec with the latest `go_live` at or before the time of the check. A check run before that date says "no version live".
2. **Run the eval by hand.** Write an invented vote in a file `vote.json` with the payload form above. Use invented company names. Do not use a real vote. Run:

   ```
   uv run vc-evals ic --stdin < vote.json
   ```

   A good vote prints one row with PASS. Change one thing, for example set the verdict to YES with Founders rated Weak. The row now says FAIL and names gate G3.
3. **Push the workflow.** Push `.github/workflows/score-vote.yml` to `main`. GitHub accepts a workflow file only from a login that has permission to change workflows. If the push is refused, use a login or token with that permission. The n8n node starts the job on `main`.
4. **Import the n8n workflow.** Import `n8n/ai-ic-vote-eval.json` into n8n.
   - Make the webhook token: `openssl rand -hex 32`. Create a Header Auth credential. Name: `X-Eval-Token`. Value: the token. Attach it to the webhook node. Keep the token for item 5.
   - Attach the existing result-token credential to `Wait: Eval Result`.
   - Attach the existing GitHub credential to `GitHub: Score Vote`.
   - Attach your Slack credential and set `YOUR_SLACK_CHANNEL` to the channel for failures.
   - Turn the workflow on. Copy its production webhook address.
5. **Add the skill to the AIVC project.** Add `skills/ai-ic-vote-eval/SKILL.md` to the project. I could not verify how skills are added to a Claude Project on your plan. Check the Claude help pages for your plan, or the project settings. In the skill file, replace the two placeholders: `<N8N_WEBHOOK_URL>` with the production address and `<N8N_WEBHOOK_TOKEN>` with the token from item 4. Do not commit the filled-in file.
6. **Test.** Send a deliberately bad invented vote to the webhook, for example one with a missing field:

   ```
   curl -X POST "<N8N_WEBHOOK_URL>" -H "X-Eval-Token: <N8N_WEBHOOK_TOKEN>" -H "Content-Type: application/json" -d @bad-vote.json
   ```

   n8n answers at once. Within a few minutes a Slack post must appear. Then send a good invented vote. No Slack post must appear. Check the Actions run on GitHub for both.
7. **Switch the project.** Replace the project's instructions with the contents of `prompts/ai_ic_v1.md`. Run one real IC vote. The IC sees the vote first. A failure shows in Slack.

**Design points.**
- The project shows the vote first and calls the skill second. The skill leaves the displayed vote as it is.
- n8n answers right away, so the IC is not delayed.
- Failures go to Slack only. A vote that passes posts nothing.
- If the call fails, the project says so in one line and tries at most once more.

**Open questions / unverified.**
1. Can a Claude Project call an outside web address? This depends on network access settings and connectors on the owner's plan. Test in item 6 with a real project, not only with curl.
2. How do skills load in a Claude Project? Check item 5 on the owner's plan.
3. Which Slack channel gets the failures? The owner decides.
4. The repo's Actions logs and workflow inputs will contain vote text. Keep the repo private, or review and delete the logs,. Set a short log retention.

**Done when:** `vc-evals ic --stdin` passes a good invented vote and fails a bad one, a bad vote sent to the webhook causes a Slack post, a good one causes none, and the project runs on `prompts/ai_ic_v1.md`.

---

## 7. Repo

```
vc-evals/
  CLAUDE.md
  README.md
  pyproject.toml          # python>=3.12, uv; deps: httpx, nltk, pydantic, typer, textstat, pysbd
  .env.example            # ATTIO_API_KEY
  .gitignore              # .env, out/, .venv
  .github/workflows/      # score-brief.yml: scores a brief for n8n; score-vote.yml: checks a vote for n8n
  docs/                   # build-guide, systems-map
  prompts/                # brief_v0.md, brief_v0.spec.toml, brief_v1.md, brief_v1.spec.toml, ai_ic_v1.md, ai_ic_v1.spec.toml
  skills/                 # ai-ic-vote-eval/SKILL.md: the AI IC member project calls it
  n8n/                    # pre-call-brief-v2-eval.json, ai-ic-vote-eval.json, no credentials
  src/vc_evals/
    attio.py              # read-only client: notes
    briefs.py             # parse a brief, run the checks (the scoring core)
    links.py              # the link check (the only network use in `score`)
    layer2/               # quality proxies, one file per measure; xkcd_words.txt
    ic.py                 # checks one AI IC member vote: format, values, gates
    cli.py                # vc-evals score | measure | ic
  fixtures/               # invented briefs and votes
  tests/                  # no network calls
  out/                    # page cache (git-ignored)
```

---

## 8. Rules

- No fund data in git. Fixtures are invented.
- Publish aggregates only, with the fund's permission.
- Attio access is read-only in the harness.
- The harness makes no LLM calls.
- No command reads or scores every brief by default. `score` needs a selector.
- Every result shows n. No percentages below n = 5.
- Template conformance (Layer 1) runs on every workflow output.
- Not in scope for v6 (LLM judges are planned for later, see section 2a): comparing AI votes with GP votes or with a baseline, trends in ratings, API server, database, vector search, MCP server, hosting, LLM judges, deck parsing, synthetic data, CI wiring, dashboards, the IC memo.

---

## 9. First Claude Code prompt (Step 3, item 1)

```
Read docs/build-guide.md in full. This repo already has docs/, prompts/, .env and .gitignore. Do not overwrite them. Add the code that section 7 shows for Step 3 only: attio.py, briefs.py, cli.py. Do not build ic.py. Build only what this prompt lists.

1. pyproject.toml (uv, python>=3.12; deps from section 7; dev: pytest, ruff). Console script `vc-evals` -> vc_evals.cli:app.
2. CLAUDE.md. .env.example. Add out/ and .venv to .gitignore.
3. src/vc_evals/attio.py: read-only async httpx client. Functions: get_brief(note_id), list_briefs(deal_id, limit=20), newest first. Each brief has note id, parent deal id, created date and body text. Only notes whose title starts with "Founder Call Brief". Bearer token from ATTIO_API_KEY. Retry with backoff on 429, honoring Retry-After. Verify the notes endpoint, its pagination, and the body format against https://docs.attio.com. Do not guess. If the API cannot list notes by deal, stop and tell me. (Attio cannot list notes by date, so there is no date selector.)
4. src/vc_evals/briefs.py: the scoring core. It takes a brief body string, a created date and the prompts directory, and returns scores. It does not know where the brief came from. Parse the body into headings and the Inputs section. It also takes the note's created date. Choose the spec by date: the prompts/*.spec.toml with the latest go_live at or before the created date. Ignore specs with no go_live. Never use the brief's Prompt line to choose, and have no default version. If no spec was live, say so and skip the spec checks. One check only for now: every required section in the spec is present and not empty (use the aliases).
5. fixtures/: 4 invented briefs (one brief_v0, two brief_v1, one brief_v1 with a missing section) and fixture spec files. Do not use the real spec files in tests.
6. src/vc_evals/cli.py: command `score`. Exactly one of --note or --deal, else an error that says so. --limit N caps a deal's briefs (default 20). `--fixtures` reads fixtures instead of the network. It prints a Markdown table with one row per brief, showing the version that was live on its created date, and n. Below n=5 it prints rows and no percentages. With 0 briefs it prints "no briefs" and does not crash. Exit code 1 if any Layer 1 check fails.
7. Tests with hand-computed expected values, including 0 briefs, the n=4 and n=5 boundary, a brief with a wrong Prompt line, the go_live boundary, and a brief from before any version was live.

Do not build the other checks. No network calls in tests. Run ruff and pytest and paste the output. Stop and ask if anything is unclear.
```
