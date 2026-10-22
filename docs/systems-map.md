# Systems map

> This document contains a brief explanation of each automation for which we are building an evaluation harness.

# Deal Intake

### Who Uses It?
General Partners of the Fund (and occasional testing by an ops user)

### What starts it?
A GP initiates a conversation in the agent interface (currently Claude), using the skill "/deal-creation".

### Inputs
Text summary of the company, that is open-ended (non-formulaic) and relevant attachments (e.g. Deck, white paper, etc.).

The skill will prompt the user for required fields if omitted from the initial summary.

### Outputs
In all cases: a boilerplate summary of proposed updates, which the user must approve before any edits are made.
If record(s) exists in Attio, when approved agent will update existing records for relevant fields.
If record(s) does not exist, when approved the agent will create new record(s) with fields populated according to information given.
If no Google Drive folder exists for the deal or it is not linked, a folder will be created and linked to the deal.

### Output Location
Attio records: Deal, Company, Person creation or upsert
Google Drive folder: linked on Attio Deal record in Google Folder field, folder created in shared Google Drive under the deals subfolder

### Failure Modes
Does not propose fields when relevant information has been provided in the GP text that begins the conversation. (actual)
Proposes incorrect information for fields (potential)
Does not find existing record and thus creates/proposes duplicates (potential)
Does not create deck folder (potential)
Does not link deck folder to appropriate Attio records (potential)
Updates before receiving permission (potential)
Does not take upsert or create actions when given permission (potential)

# Pre-call Brief

### Who Uses It?
General Partners of the Fund and investors

### What starts it?
(Live) Manual workflow trigger in Attio > hits n8n webhook, which uses (among other things) an Anthropic agent with limited tool calls to perform research.
(Future State) Attio workflow automatically triggered whenever a deal is moved to "Founder Call" in Attio

### Inputs
Attio deal record information, company-provided documentation (e.g. deck or white paper) stored in shared Google Drive.

### Outputs
A note on the Deal Record that follows format given in agent instructions.

### Output Location
A note on the Attio deal record.

### Failure Modes
Poor readability, high technicality (actual)
Irrelevant information/points seem to earn a spot based on a quota instead of relevance (actual)
Agent surpasses tool call budget (seemingly to meet a budget)(actual)
Automation failures(potential)
No strong guardrails against invocations, which could waste API credit budget (actual)

# AI IC Member

### Who Uses It?
General Partners of the Fund (and occasional testing by an ops user)

### What starts it?
After the open doors session of an IC, GP initiates a conversation in the AI IC Member project in Claude.
(future state) Agent can join IC calls via integration without need for manual transcript pasting.

### Inputs
#### First pass (facts only)
Company artifacts (e.g. deck, white paper, etc.) from google drive or hyperlink.
Web-based factual information.
#### Second pass (includes opinion)
IC Memo (located in Google Drive Folder).
IC presentation deck (located in Google Drive folder).
Open door IC session transcript.
#### Closed door session
Back and forth text inputs and documents with GP (Analysis has already been completed and initial decision made. High bar for updates at this point).

### Outputs
Analysis in templated format within the Claude app, including verdict and confidence.
Explanation of analysis when prompted.
Potential for new analysis/opinion if provided new material facts.
Vote(s) for AI IC member and partner(s) if /vote skill invoked in the conversation.

### Output Location
Analysis in Claude app.
Votes (with analysis) recorded under custom Votes object in Attio.

### Failure Modes
Drift towards the middle in test cases on confidence score, i.e. always 2/3 (actual)
Gates are not respected when restricting potential verdicts (potential)
HISTORICAL BACKFILL ONLY: pulls data sources from after the IC date for determining its verdict (actual)
One pass bias: tends to favor the verdict it leans towards after reviewing facts only, and will use provided information to justify that initial bias (actual)
Vote doesn't record (potential)

# Votes

### Who Uses It?
General Partners of the Fund and AIIC Member

### What starts it?
GP initiates a conversation using the skill "/vote" in Claude.

Either happens:
1. in the context of an AI IC member conversation, in which case the AI IC member vote will be generated in addition to GP votes.
2. a normal conversation in the Claude interface where the skill is invoked.

### Inputs
Conversation context if invoked in AI IC discussion.
vote: Yes | No | Conditional
conviction: 1 | 2 | 3
party: a GP's name (or AI VC if done within AI IC discussion)
rationale: long-form text explaining the reasoning

### Outputs
Proposal votes according to template provided in instructions.
Votes in the form of a custom Attio vote object record for each vote if the proposal is approved by the user.

### Output Location
Attio Vote record, which is associated with deal records.

### Failure Modes
Votes created without approval (potential)
Votes not associated with correct record (potential)