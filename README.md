# vc-evals

Instructions and checks for the facts and analysis that an AI writes at a venture capital fund. The files here are a simplified version of the prompts and evaluation harness I developed at a working VC fund.

This repo provides instructions and monitoring processes for two things:

1. **The brief.** A short research note on a startup, written before an investor has a call with its founders.
2. **The AI Investment Committee Member recommendation.** An AI that sits on the fund's investment committee and votes on whether to invest.

The scripts in this repo do not author output. They consume what the AI wrote and ask: *does this have the shape we asked for, does it read plainly, and does it agree with itself?* They answer with plain code: string checks, counting, a few small libraries. No AI is used to check the AI.

If you are a software engineer who has never worked in venture capital and has not spent much time with AI tools, this README is for you.

---

## Contents

- [First, what is this business?](#first-what-is-this-business)
- [Second, what is the AI doing here?](#second-what-is-the-ai-doing-here)
- [The first principle: do not fool yourself](#the-first-principle-do-not-fool-yourself)
- [Quick start](#quick-start)
- [Eval 1: the brief (`score` and `measure`)](#eval-1-the-brief-score-and-measure)
- [Eval 2: the AI IC member's vote (`ic`)](#eval-2-the-ai-ic-members-vote-ic)
- [How it runs for real](#how-it-runs-for-real)
- [Changing a prompt: spec files and `go_live`](#changing-a-prompt-spec-files-and-go_live)
- [The house rules, and why](#the-house-rules-and-why)
- [What's in the repo](#whats-in-the-repo)
- [License](#license)

---

## First, what is this business?

A **seed fund** gives money to very young companies, often just a few people with an idea and a prototype, in return for a slice of ownership. Most of those companies will fail. A few will do very well, and one very good one can pay back the whole fund. So the job is not to avoid failures. The job is to not miss the rare big win.

Here is a simplified view of how a company moves through the fund, and where the AI comes in. Real deals loop and branch more than this:

```
 a company is found ──► a "deal" is logged in the CRM
                              │
                              ▼
                     the AI writes a BRIEF  ◄── Eval 1 checks this
                              │
                              ▼
                  investor has a FOUNDER CALL
                  (often several, over weeks)
                              │
                              ▼
              investors and partners do DUE DILIGENCE:
              more calls, customer and expert checks,
              deeper research
                              │
                  worth investing? ── no ──► pass on the deal
                              │ yes
                              ▼
              they prepare materials for the committee
                              │
                              ▼
                  the INVESTMENT COMMITTEE meets
              (partners vote, and so does an AI member) ◄── Eval 2 checks the AI's vote
                              │
                              ▼
                       invest, or don't
```

The words you'll meet:

| Word | What it means |
|---|---|
| **Deal** | One possible investment in one company. It is a record in the CRM. |
| **CRM** | A database of companies, people and deals. The fund I built this for used [Attio](https://attio.com), and that is the software behind the examples here, but the setup applies to any CRM. A note attached to a deal record is where a brief lives. From here on, this README just says "the CRM". |
| **GP** (General Partner) | One of the people who run the fund and make investment decisions. |
| **Founder call** | The first proper conversation between an investor and the people who started the company. |
| **Deck** | The slide presentation the founders send. |
| **IC** (Investment Committee) | The meeting where the partners decide whether to invest. Each member votes. |
| **Vote** | YES, NO or CONDITIONAL (yes, if some stated condition is met), plus a **conviction** of 1, 2 or 3 (how sure the voter is). |
| **Round, instrument, ask, post-money** | The terms of the investment: what stage of fundraising, what kind of contract (a SAFE, for example), how much the company is raising, and what the company is worth after the money goes in. |
| **Fund-returner** | A company that could, on its own, pay back the whole fund. |

That's enough VC for this README.

---

## Second, what is the AI doing here?

An **LLM** (large language model) is a program that takes text in and writes text out. You give it a **prompt**: a page of instructions like "write a brief with these five headings, under 800 words, no tables". It writes something back.

Now here's the trouble, and it's the reason this repo exists. With ordinary code, you call a function twice with the same input and you get the same answer. You can write a unit test. With an LLM, you give it the same prompt twice and you get two different answers. The web pages it reads change from day to day too. And when it gets something wrong, it doesn't throw an exception. It writes something that *looks* fine.

So how do you know if it's doing its job? You need an **eval**: a test of the output, run over and over on real outputs, that tells you how often the AI did what you asked. Some evals are simple code ("are all five headings there?"). Some use a second AI as a grader. That's called an **LLM judge**. This repo only has the simple code kind, for now, on purpose.

A few more tool words:

| Word | What it means |
|---|---|
| **Automation / orchestration software** | A tool for wiring services together into automated workflows, like a visual programming canvas. Mine was [n8n](https://n8n.io); any equivalent works. In my setup the brief is written by a workflow that calls an LLM. |
| **AI client / project** | A workspace in your LLM app with standing instructions. Mine was a [Claude](https://claude.ai) Project; any client that supports standing instructions works. The AI IC member is such a project, with the instructions in `prompts/ai_ic_v1.md`. |
| **Skill** | A small instruction file an AI can follow to do one job. Here, `skills/ai-ic-vote-eval/SKILL.md` tells the AI IC member how to send its vote off to be checked. |
| **Webhook** | A URL that, when something sends data to it, starts a workflow. |
| **Spec file** | A small file in `prompts/` that says, as data, what one version of a prompt must produce: the headings, the limits, the allowed values. The checks read it. None of these rules are written into the code. |

---

## The first principle: do not fool yourself

> "The first principle is that you must not fool yourself — and you are the easiest person to fool." — Richard Feynman

With evals it's very easy to fool yourself. You write a check, it passes, and you feel the AI is good. But all you've shown is that the AI passes *that check*. So let me be completely clear about what these checks can and cannot tell you.

The checks come in three layers:

| Layer | What it asks | Can it fail an output? | Built? |
|---|---|---|---|
| **1. Template conformance** | Did the output follow the rules? Headings there, limits kept, values from the allowed list, verdict allowed by the rules. | Yes | Yes, for briefs and votes |
| **2. Quality proxies** | Is the brief easy to skim? Word counts, sentence lengths, readability, jargon, bullets, repeated points. | No. Reported only. | Yes, for briefs |
| **3. LLM judge** | Are the claims supported by the sources, or did the AI make something up (a hallucination)? Are these the *right* points? Are the real risks there? | — | Not yet. Planned: LLM judges will be added later to catch hallucinations and to evaluate content more closely. None exist today. |

**What a pass means:** the output has the format we specified and agrees with itself (for example, a vote doesn't contradict its own ratings). For briefs, the Layer 2 numbers also give an indication of readability, but they are reported and never decide a pass.

**What a pass does not mean:** that anything in it is true, that the points are the right ones, or that the investment decision is good. Code cannot tell you a claim about a company is true. When you hear "the brief passed", hear "the brief has the right shape". No more.

That gap is what the planned LLM judges (Layer 3) are for: checking claims against their sources to catch hallucinations, and judging the content more closely than shape and readability can. Until they exist, treat the content as unchecked.

Two more ways we try not to fool ourselves:

- **Every result shows n**, the number of things checked. And **below n = 5, no percentages are printed.** If three out of four briefs pass and I tell you "75%", that sounds like a measurement. It isn't. It's four coin flips. So below five you get the rows, and you can look at them yourself.
- **The AI's statements about itself are claims, not facts.** A brief ends with a line like `Prompt: brief_v1` and `Model: ...`. The model wrote those lines. It can be wrong. So they never decide which rules a brief is checked against. (More on how that *is* decided [below](#changing-a-prompt-spec-files-and-go_live).)

---

## Quick start

You need Python 3.12 and [uv](https://docs.astral.sh/uv/) (a fast Python package manager).

```bash
git clone https://github.com/gregoryrichens/vc-evals.git
cd vc-evals
uv sync                                  # install everything
uv run ruff check . && uv run pytest -q  # lint and run the tests (no network needed)
```

Now run both evals on the invented examples in `fixtures/`. You don't need any accounts or keys for this:

```bash
# Eval 1: score four invented briefs, as if they came from one deal in the CRM
uv run vc-evals score --deal deal-1 --fixtures

# Eval 2: check one invented AI IC vote
uv run vc-evals ic --stdin < fixtures/ic/pass_no.json
```

To read real briefs from your CRM, you need an API token with **read-only** access to records and notes. The bundled reader (`src/vc_evals/attio.py`) is written for the CRM I used, so for another CRM, swap that one file for a reader of the same two calls (fetch one note, list one deal's notes), or skip it and use `--stdin`. Put the token in a file called `.env` at the repo root (it's git-ignored):

```
# The name of this variable, and where you get the token, depend on your CRM.
# The bundled reader is written for the CRM I used, so it looks for this name.
# If you swap in a reader for another CRM, use whatever name that reader expects.
ATTIO_API_KEY=your-token-here
```

You can also set it as an environment variable instead. (The variable name matches the bundled reader.)

---

## Eval 1: the brief (`score` and `measure`)

### What a brief is

Before a founder call, an automated workflow asks an LLM to research the company (the CRM record, the deck in Google Drive, a few web searches) and write a short brief. It's saved as a note on the deal in the CRM, titled `Founder Call Brief — <date>`. The current prompt is `prompts/brief_v1.md`, and it asks for five sections:

```markdown
## What is it?
## Founders
## Market
## Competitors
## Follow Up

## Inputs
Deck: examplco-deck.pdf
Other Company Materials: none
Web: https://example.com/planters
Prompt: brief_v1
Model: example-model
```

The **Inputs** section at the end lists what the AI says it used. Under 800 words, not counting Inputs. No tables.

When the partners were asked what makes a bad brief, they said: too technical to skim, padded with points that seem to be there to fill a quota, and missing what matters. Layer 1 checks that the brief follows the template. Layer 2 measures the "too technical" and "padded" parts as numbers.

### Running it

`score` needs **exactly one** of three ways to choose which briefs to check:

```bash
uv run vc-evals score --note <note-id>             # one CRM note
uv run vc-evals score --deal <deal-id> --limit 1   # one deal's briefs, newest first (default limit 20)
pbpaste | uv run vc-evals score --stdin            # one brief piped in as text
```

There is no "score everything" option. That's on purpose: an eval should run on a set of inputs you chose, not on whatever happens to be in the database.

Other options:

- `--fixtures` reads the invented briefs in `fixtures/` instead of the CRM.
- `--links` also fetches each `Web:` URL in the Inputs section and reports whether it loaded. It's off by default because it uses the network. A dead link is reported, not failed. A page loading tells you the page exists. It doesn't tell you the brief described it truthfully.
- `--prompts-dir` points at a different folder of spec files.

### Reading the output

Here's the real output on the fixtures:

```
| Note | Deal | Created | Prompt | Words | Result | Detail |
|---|---|---|---|---|---|---|
| n-bad | deal-1 | 2026-10-17 | brief_v1 | 30 | FAIL | missing: Competitors |
| n-v1b | deal-1 | 2026-10-16 | brief_v1 | 51 | pass | - |
| n-v1a | deal-1 | 2026-10-15 | brief_v1 | 58 | pass | - |
| n-v0 | deal-1 | 2026-09-20 | brief_v0 | 41 | pass | - |

n = 4 (below 5: rows only, no percentages)
```

Look at the **Prompt** column. The brief from September was checked against `brief_v0`, and the October ones against `brief_v1`. The code didn't read that from the brief. It worked it out from the date the note was created (see [spec files](#changing-a-prompt-spec-files-and-go_live)). A brief from before any version went live says `no version live`. That isn't a failure. We just have no rules to check it against.

**Layer 1 checks** (all from the spec file):

| Check | Fails when |
|---|---|
| Sections | A required heading is missing, or present but empty. Headings match ignoring case, `?` and `-`, and the spec can list aliases (`Follow-Up Questions` counts as `Follow Up`). |
| Word limit | More words than `max_words`, not counting the Inputs section. |
| Tables | A Markdown table, when the spec says no tables. |
| Heading levels | A heading at a level the spec doesn't allow. |
| Inputs | No Inputs section; a required line missing; a line repeated that shouldn't be; `Prompt:` not equal to the spec's version; a `Web:` value that isn't a URL. |

If the brief's own `Prompt:` line disagrees with the version it was checked against, the Detail column says so.

**Exit codes:** `0` if nothing failed (a "no version live" row doesn't count as a failure), `1` if any brief failed Layer 1, `2` if you gave the wrong number of selectors. That makes `score` usable as a CI step.

### Layer 2: quality proxies

Under the Layer 1 table, `score` prints a second table of numbers for each brief. These never pass or fail anything and never change the exit code. They're measurements. We don't yet know which of them separate good briefs from bad ones. Finding out needs a handful of briefs that a partner has rated good and bad, and that hasn't been done yet. So for now: compare the numbers between briefs, and don't read any one of them as a grade.

All six read the brief **without its Inputs section**:

| Measure | What it measures | How |
|---|---|---|
| `words_per_section` | Words in each section, and the longest section. Padding shows up as one fat section. | Our own code |
| `sentence_length` | Number of sentences, mean words per sentence, longest sentence. A bullet with no full stop counts as one sentence. | [pySBD](https://pypi.org/project/pysbd/) finds sentence boundaries |
| `readability` | Flesch Reading Ease (higher is easier; 60–70 is plain English) and Flesch-Kincaid grade (a US school grade). | [textstat](https://pypi.org/project/textstat/). Made for prose, so bullet-heavy briefs may score oddly. |
| `jargon` | Words not on the [XKCD Simple Writer](https://xkcd.com/simplewriter/) list, as a count and per 100 prose words. A stand-in for "too technical". | Our own code and the word list in `layer2/xkcd_words.txt` |
| `bullets_per_section` | List items in each section, and the most in any one section. | Our own code |
| `near_duplicates` | Pairs of sentences (four or more words) that are at least 80% alike. A stand-in for "said the same thing twice". | Python's `difflib` |

A bit more about jargon, because it's the cleverest and the most likely to mislead you. The XKCD list is the roughly 1,000 most common English words (3,616 forms with plurals and tenses) that Randall Munroe used to write *Thing Explainer*. Anything not on it counts as jargon. That list is small, so ordinary business words like "founders" and "subscription" count as jargon too. That's fine as long as you only compare rates between briefs. Words that are capitalised in the middle of a sentence are taken to be names and skipped. All-capitals words like `FPGA` are not skipped, because those are exactly the acronyms we want to catch.

To run one measure alone and see its working (which sentence was longest, which words counted as jargon), use `measure` with the same one-selector rule:

```bash
uv run vc-evals measure jargon --note <note-id>
pbpaste | uv run vc-evals measure readability --stdin
uv run vc-evals measure jargon --note n-v1a --fixtures
```

The measure names are the ones in the table above.

---

## Eval 2: the AI IC member's vote (`ic`)

### What the AI IC member does

The AI IC member is an AI project that votes alongside the human partners. Its instructions (`prompts/ai_ic_v1.md`) take it through eight steps:

1. Read the facts: deck, call transcripts, public record.
2. Run five **integrity checks**: full-time founders, clean IP, no litigation, no criminal association, sound round mechanics. Each is `PASS`, `FAIL` or `NOT VISIBLE`.
3. Do the **fund-returner math**: given the price, how big would this company have to get to pay back the fund?
4. Score the **Four Forces**: Market & Timing, Secret/Monopoly, Founders, Capital Efficiency. Each is `Not visible`, `Weak`, `Adequate` or `Exceptional`.
5. Apply seven **gates**: rules that limit which verdicts are allowed (below).
6. Read the partners' analysis.
7. Argue both sides.
8. **Vote**, in a fixed format.

After it shows the vote to the committee, it sends two things off to be checked: the vote text exactly as shown, and its own ratings from steps 2 to 5.

### The gates, in plain words

The gates are the most interesting part. They're rules the AI sets itself before it votes, like "if the founders look weak, you must vote no." Here they are, from `prompts/ai_ic_v1.spec.toml`:

| Gate | If… | …then the verdict must be |
|---|---|---|
| G1 | any integrity check FAILed | NO |
| G2 | there's no credible path to the exit size the fund needs | NO |
| G3 | Founders is Weak or Not visible | NO |
| G4 | neither Market & Timing nor Secret/Monopoly is Adequate or better | NO |
| G5 | Market & Timing or Secret/Monopoly is Weak, and Founders isn't Exceptional | NO |
| G6 | two or more forces are Not visible, and none is Exceptional | NO |
| G7 | two or more forces are Not visible | NO or CONDITIONAL (not YES) |

If several gates trip, every one of them must allow the verdict, so the strictest one wins.

### What is checked

| Check | What it tests |
|---|---|
| **Format** | The first line has five values: `COMPANY / ROUND / INSTRUMENT / ASK / POST-MONEY`. Then the labelled lines in order: VERDICT (YES, NO or CONDITIONAL), CONVICTION (1, 2 or 3), THESIS IN ONE SENTENCE, STRONGEST CASE AGAINST MY OWN VOTE, RATIONALE. RATIONALE has six named bullets in order, and "The few decisive facts" is tagged OBSERVED or CLAIMED. A NO vote says "no, now" or "no, ever". 400 to 700 words. No gate codes ("G3", "Gate 3") in the text, because the committee should read the reason, not a code. |
| **Values** | Every integrity check, every force and the exit pathway is present and has an allowed value. No unknown keys. |
| **Gates** | The verdict is one that every tripped gate allows, given the AI's own ratings. |

### Running it

`ic` reads one JSON payload from standard input:

```json
{
  "output": "Examplo Ltd / Seed / SAFE / $500,000 / $8,000,000\n\nVERDICT: NO\n\nCONVICTION: 2\n...",
  "checks": {
    "integrity": {
      "full_time_founders": "PASS",
      "clean_ip": "PASS",
      "no_litigation": "NOT VISIBLE",
      "no_criminal_association": "PASS",
      "round_mechanics": "PASS"
    },
    "forces": {
      "market_timing": "Adequate",
      "secret_monopoly": "Weak",
      "founders": "Weak",
      "capital_efficiency": "Adequate"
    },
    "exit_pathway": "credible"
  }
}
```

```bash
uv run vc-evals ic --stdin < fixtures/ic/pass_no.json
```

```
| Company | Prompt | Words | Verdict | Conviction | Result | Detail |
|---|---|---|---|---|---|---|
| Northwind Pottery Labs | ai_ic_v1 | 452 | NO | 2 | pass | - |

n = 1 (below 5: rows only, no percentages)
```

Now let's break one. Take the invented YES vote in `fixtures/ic/pass_yes.json`, change `"founders"` from `"Adequate"` to `"Weak"`, and run it again:

```
| Northwind Pottery Labs | ai_ic_v1 | 432 | YES | 3 | FAIL | gate G3: Founders is Weak or Not visible, so the verdict must be NO (vote says YES) |
```

The AI said the founders were weak, and then voted yes. Its own rules don't allow that, and the check caught it.

**Exit codes:** `0` pass, `1` fail (format, values, gates, or a payload that isn't valid JSON), `2` if you forgot `--stdin`. The vote is checked against the spec that is live *now*, at the time of the check. If none is live yet, the row says `no version live`, which is not a failure.

### What this cannot catch

This is important, so I'll say it plainly. **The gate check tests the vote against the AI's own ratings.** It catches the AI contradicting itself. It does not catch the AI being wrong.

Think of a student's maths exam. The check sees the student write "x = 3" on one line and then use "x = 5" on the next, and marks that wrong. But if the student made a mistake earlier and got "x = 3" when the real answer was 7, and then carried on perfectly, the check marks every line right. If the AI rates mediocre founders "Adequate" and votes YES, everything is consistent and the vote passes.

Also not checked: whether the thesis is any good, whether a CONDITIONAL vote has at most three conditions, and whether the AI agrees with the human partners. Agreeing with the partners isn't the same as being right, and there aren't yet enough votes to compare anyway.

---

## How it runs for real

On your laptop you pipe text into the command. In production, the automation software and a CI job (GitHub Actions in my setup) do the piping. The harness itself never changes: it's the same `uv run vc-evals ... --stdin` either way.

### The brief, scored before it's saved

```
CRM: "write a brief"
   │
   ▼
Automation workflow ── the LLM writes the brief
   │
   ├──► starts CI job  .github/workflows/score-brief.yml
   │        runs: vc-evals score --stdin
   │        sends the result back to the workflow
   │
   ▼  (the workflow waits up to 3 minutes)
The workflow writes the CRM note: the brief, then an "Eval result" section
```

If the CI job is slow or broken, the note is still written with just the brief. The eval should never stop an investor getting their brief. The workflow export (n8n format, from my setup) is `n8n/pre-call-brief-v2-eval.json`.

### The vote, checked after the committee has seen it

```
AI IC member (AI project) shows its vote to the committee
   │
   ▼
calls the skill skills/ai-ic-vote-eval/ ── POSTs {output, checks} to an automation webhook
   │
   ▼
The workflow answers "received" at once, so nobody waits
   │
   ├──► starts CI job  .github/workflows/score-vote.yml
   │        runs: vc-evals ic --stdin
   │        sends {exit_code, output} back to the workflow
   │
   ▼
failure ──► a chat message           pass ──► nothing
```

Order matters here. The committee sees the vote first and the check runs second, so the check can't hold up a meeting or change a vote. The workflow export (n8n format) is `n8n/ai-ic-vote-eval.json`.

Setting these up needs three different secrets (a webhook token, a result token and a CI token) that go in different places. It's easy to mix them up. The step-by-step setup is in Steps 4 and 5 of [docs/build-guide.md](docs/build-guide.md).

One warning: the brief and vote text are passed to the CI job as workflow inputs, so they appear in its logs. Keep the repo that runs the workflows private, or keep log retention short.

---

## Changing a prompt: spec files and `go_live`

Prompts change. When they do, the rules for checking their output have to change too. But a brief written in September under the old prompt shouldn't be failed against October's rules. How do you pick the right rules for each output?

The answer is a date. Each spec file in `prompts/` has a `go_live` timestamp:

```toml
version = "brief_v1"
go_live = "2026-10-14T12:00:00-06:00"
```

A brief is checked against **the spec with the latest `go_live` at or before the moment its note was created.** It's like marking an exam against the syllabus that was in force on the day the exam was sat, not against the one the student says they studied. There is no fallback. If nothing was live yet, the answer is "no version live".

Brief specs are files named `brief_*.spec.toml`. AI IC specs are named `ai_ic_*.spec.toml`. Each kind is chosen separately.

To roll out a new prompt version:

1. Save the new prompt as `prompts/<name>_v2.md`.
2. Copy the previous spec to `prompts/<name>_v2.spec.toml` and change what the new prompt asks for: headings, Inputs lines, word limits, allowed values, gates.
3. Set `go_live` to the exact moment you switch production to the new prompt. Use a full timestamp with a time zone if two versions go live on the same day.
4. Run the tests. Then switch production.

You never touch the Python. The headings, limits, allowed values and gate rules all live in the spec files, and the AI IC spec has a small condition language for gates that's documented in its comments. If you want to use this at your own fund with your own templates, that's where you'd start.

---

## The house rules, and why

These are in [CLAUDE.md](CLAUDE.md) for the AI coding assistant that helps build this repo. They're good rules for people too.

| Rule | Why |
|---|---|
| **No real fund data in git.** No company names, deal IDs, brief text, votes or decks. Every fixture is invented. `.env` and `out/` are git-ignored. | It's confidential information about founders and their companies, and once it's in git history it's very hard to remove. |
| **CRM access is read-only.** | A checker that can write to the CRM could break what it's checking. |
| **No LLM calls in this repo.** | The checks should be cheap, fast, and give the same answer every time. And you can't fully trust one AI to grade another. |
| **No command reads every brief by default.** You must choose. | An eval runs on inputs you chose. A full sweep is slow, and it reads confidential data nobody asked for. |
| **Every command runs with zero examples, and every result shows n.** | The automations are new. There may be only one brief. The tools must still work and say exactly how little they've seen. |
| **Tests never call live APIs.** | Tests must run anywhere, including CI, without keys or a network. |
| **Rules live in spec files, not code.** | So a prompt change is a data change that anyone can review. |

---

## What's in the repo

```
vc-evals/
  src/vc_evals/
    cli.py            # the commands: score, measure, ic
    briefs.py         # parse a brief and run the Layer 1 checks; picks the live spec
    ic.py             # check one AI IC vote: format, values, gates
    attio.py          # read-only CRM client (written for Attio): fetch one note, or one deal's briefs
    links.py          # the optional link check (the only network use in score)
    layer2/           # one file per quality measure, plus the XKCD word list
                      # and a bundled pronouncing dictionary, so nothing is downloaded
  prompts/            # each prompt version (.md) and its spec file (.spec.toml)
  skills/             # the skill the AI IC member calls to send its vote
  n8n/                # automation workflow exports (n8n format, no credentials)
  .github/workflows/  # score-brief.yml and score-vote.yml, started by the workflow
  fixtures/           # invented briefs, specs and votes for the tests
  tests/              # pytest; no network
  docs/
    build-guide.md    # the full plan, decisions and setup runbooks
    systems-map.md    # each automation: who uses it, inputs, outputs, how it fails
```

The prompts in `prompts/` are the ones the fund used, with fund-specific details removed, published on purpose so you can see what the checks are checking against. (The fund's sizes in the AI IC prompt are blanked out as `$X`.)

---

## License

This project is released under the **MIT License**. See [LICENSE](LICENSE) for the full text.

In short: you may use, copy, change, merge, publish, distribute, sublicense and sell copies of this software, for free, for any purpose, commercial or not. You must keep the copyright notice and the license text with any substantial copy. The software comes with no warranty of any kind.

Two bundled data files come from other people and keep their own licenses. MIT does not cover them:

- **`src/vc_evals/layer2/xkcd_words.txt`**: the XKCD Simple Writer word list by Randall Munroe, from [xkcd.com/simplewriter](https://xkcd.com/simplewriter/). xkcd content is licensed under [CC BY-NC 2.5](https://creativecommons.org/licenses/by-nc/2.5/): attribution required, **non-commercial use only**. If you use this project commercially, replace this file with a word list you're licensed to use. Only the `jargon` measure reads it.
- **`src/vc_evals/layer2/nltk_data/corpora/cmudict/`**: the Carnegie Mellon University Pronouncing Dictionary, Copyright (C) 1993–2008 Carnegie Mellon University, under a BSD-style license. Its full terms are in the `README` in that folder. textstat uses it to count syllables.
