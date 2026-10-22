---
name: ai-ic-vote-eval
description: Use right after the AI IC member has displayed a complete vote in the Step 8 format. Sends the vote and the member's own ratings to the eval webhook, once per vote.
---

# AI IC vote eval

## When to call

- After the complete vote is displayed to the IC. Not before.
- One call per vote. A changed vote after the IC discussion is a new vote and gets its own call.
- Do not alter the displayed vote. Do not show the payload to the IC.

## Payload

```json
{
  "output": "<the full vote text exactly as shown to the IC>",
  "checks": {
    "integrity": {
      "full_time_founders": "PASS | FAIL | NOT VISIBLE",
      "clean_ip": "PASS | FAIL | NOT VISIBLE",
      "no_litigation": "PASS | FAIL | NOT VISIBLE",
      "no_criminal_association": "PASS | FAIL | NOT VISIBLE",
      "round_mechanics": "PASS | FAIL | NOT VISIBLE"
    },
    "forces": {
      "market_timing": "Not visible | Weak | Adequate | Exceptional",
      "secret_monopoly": "Not visible | Weak | Adequate | Exceptional",
      "founders": "Not visible | Weak | Adequate | Exceptional",
      "capital_efficiency": "Not visible | Weak | Adequate | Exceptional"
    },
    "exit_pathway": "credible | not credible"
  }
}
```

Each field takes exactly one of the listed words, spelled and capitalised as shown. Take the values from the ratings recorded in Step 2 (integrity), Step 4 (forces) and Steps 3 and 5 (exit pathway). Do not recompute them.

## How to send

Build the JSON with `json.dumps` so it is exact, then POST it:

```python
import json, urllib.request

# Owner fills in: N8N_WEBHOOK_URL (the n8n production webhook URL for
# path ai-ic-vote-eval) and N8N_WEBHOOK_TOKEN (the Header Auth value).
N8N_WEBHOOK_URL = "<N8N_WEBHOOK_URL>"
N8N_WEBHOOK_TOKEN = "<N8N_WEBHOOK_TOKEN>"

payload = {"output": VOTE_TEXT, "checks": CHECKS}  # fill from the vote and ratings

req = urllib.request.Request(
    N8N_WEBHOOK_URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "X-Eval-Token": N8N_WEBHOOK_TOKEN,
    },
    method="POST",
)
with urllib.request.urlopen(req, timeout=20) as resp:
    print(resp.status, resp.read().decode())
```

With curl, write the `json.dumps` output to a file and send it with `--data @file`, using the same two headers.

## Reply

- HTTP 202 `{"ok": true, "received": true}`: done. Say nothing about it and continue.
- HTTP 400 with an `error` string: the payload was malformed. Fix the payload once and resend once.
- Any other failure: say "The vote eval call failed." in one line and stop.

## Rules

- One call per vote.
- Do not wait for or report the eval result. A failure arrives in Slack.
- Do not change the vote because of the call.

## Example (invented, not a real vote)

Text is shortened for illustration. A real `output` is the full vote, 400 to 700 words.

```json
{
  "output": "Examplo Ltd / Seed / SAFE / $500,000 / $8,000,000\n\nVERDICT: NO\n\nCONVICTION: 2\n\nTHESIS IN ONE SENTENCE: Placeholder thesis.\n\nSTRONGEST CASE AGAINST MY OWN VOTE: Placeholder case.\n\nRATIONALE:\n- Structure / integrity gate: Placeholder.\n- Fund-returner math + year-10 picture: Placeholder.\n- Four Forces: Placeholder.\n- The few decisive facts: Placeholder (OBSERVED).\n- Why No: No, now. Placeholder.\n- Material things I could not see: Placeholder.",
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
