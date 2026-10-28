# n8n Workflows as Code (GTM Engineering)

**Version GTM automations in GitHub, read diffs in plain English, stop secrets landing in git — and review workflow changes for CRM risk before they hit production.**

> Built by Rubia Naseem, GTM Engineer (12+ yrs CRM/RevOps, HubSpot & Salesforce).

---

## The pain point

n8n's built-in history lives inside n8n. Most teams download JSON now and then. Backups are easy. Governance is not: hard-coded HubSpot tokens in HTTP nodes, lifecycle writes with no error branch, and nobody owning the blast radius when an inbound router changes.

- *"Hardcoding API keys in nodes is a recipe for disaster (especially if you export/share blueprints)."* ([r/n8n: My Checklist For Moving from It Works to Production Ready](https://www.reddit.com/r/n8n/comments/1pswpkn/my_checklist_for_moving_from_it_works_to/))
- *"Monitoring tells you a workflow ran. It doesn't tell you who answers for it."* ([r/n8n: Built a governance layer for n8n](https://www.reddit.com/r/n8n/comments/1vhsswf/built_a_governance_layer_for_n8n_who_owns_each/))

---

## What it does

- **Version pack:** `n8n_versioner.py` sync / diff / clean / secret redact / inventory for a multi-node GTM workflow pack (inbound routing, event-lead cleanup, closed-won handoff)
- **Human diffs:** nodes added/removed/renamed, exact setting changes, rewires
- **Secret guard:** finds API keys typed into nodes, redacts them, strips pinned test data
- **GTM review agent:** `gtm_workflow_review.py` reviews a proposed workflow (or PR-style diff) for secrets, hard-coded emails, missing error branches, unsafe CRM lifecycle writes — writes a review brief + checklist CSV
- **Works with no API key / no n8n connection** via `sample_exports/` and `sample_review/`; Claude only polishes summaries if you add a key

---

## Where each step runs

1. **GitHub** holds the code and workflow JSON. Clone or download the ZIP.
2. **n8n** is where workflows run. Nothing here changes them; you export into `exports/` or let sync pull with an n8n API key.
3. **Terminal** runs `python n8n_versioner.py sync` and `python gtm_workflow_review.py`.
4. **Claude is optional** for plain-English summaries / review polish.
5. **You, then Git.** Read the review brief, fix blockers, commit.

**These tools never write to n8n.**

---

## Quick start

```bash
git clone https://github.com/rubianaseem/n8n-workflows-as-code.git
cd n8n-workflows-as-code
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python n8n_versioner.py sync          # sample exports, no keys
python gtm_workflow_review.py --no-llm   # review the sample proposed change
```

---

## Example output

Review agent on the sample proposed inbound router (no API key):

```text
GTM WORKFLOW REVIEW  |  Inbound lead routing  |  built-in rules (no API key)
Findings: 1+ block, several warn
  BLOCK secrets_or_hygiene     Bearer token hard-coded in a header
  BLOCK unsafe_crm_write       HubSpot: force lifecycle to customer
  WARN  hardcoded_email        escalate to ae-oncall@acme.example
```

Files: `out/gtm_review_brief.md`, `out/gtm_review_checklist.csv`.

---

## Commands cheat sheet

```bash
python n8n_versioner.py sync --source sample
python n8n_versioner.py audit workflows/
python gtm_workflow_review.py --no-llm
python n8n_versioner.py review --no-llm   # same review via subcommand
```

## Sample GTM workflow pack

Committed under `workflows/` (and raw samples under `sample_exports/`):

- Inbound lead routing — form trigger, enrich, segment, round-robin owner
- Event lead cleanup — post-event hygiene before CRM import
- Closed-won handoff — CS kickoff on Closed Won

`sample_review/` holds a deliberately risky proposed change so you can practise a GTM PR review without touching production n8n.

## More

- [SETUP.md](SETUP.md): n8n API key, Claude, CI example under `ci/` (not `.github/workflows`), extending rules
- [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md): how a GTM eng versions automation and reviews a change
- [docs/DETAILS.md](docs/DETAILS.md): commands, quotes, cost, stack swap, production notes
- [WORKFLOWS.md](WORKFLOWS.md): generated inventory
