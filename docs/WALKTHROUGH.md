# Walkthrough: versioning GTM automation like code

## Why GTM engineering cares

Inbound routers, event-lead cleanups, and closed-won handoffs write to HubSpot and ping Slack. A silent failure or a hard-coded token is a CRM incident. Treat the JSON like application code: review it, redact it, and keep a history outside n8n.

## 1. Keep a pack in `workflows/`

This repo ships three educational GTM flows:

- `inbound-lead-routing.json` — form trigger, enrich, segment, round-robin
- `event-lead-cleanup.json` — post-event list hygiene
- `closed-won-handoff.json` — CS handoff on closed-won

Run `python n8n_versioner.py sync` against `sample_exports/` with no n8n connection.

## 2. What `sync` does

1. **pull** — API, `exports/`, or `sample_exports/`
2. **diff** — plain-English change summary (Claude optional)
3. **audit** — secrets, pinData, orphans, missing error workflow
4. **clean** — strip volatile fields, redact secrets
5. **inventory** — refresh `WORKFLOWS.md`
6. **changelog** — append `CHANGELOG.md`

## 3. Review before you merge

`python gtm_workflow_review.py` compares a baseline under `workflows/` to a proposed JSON (see `sample_review/`). It layers GTM checks on top of the versioner audit:

| Category | Why it matters |
| --- | --- |
| `secrets_or_hygiene` | Tokens in git get copied forever |
| `unsafe_crm_write` | Automation forcing Customer/Opportunity corrupts funnel math |
| `hardcoded_email` | Staff leave; routing breaks |
| `missing_error_branch` | HubSpot 429s leave half-updated contacts |
| `structure` | Orphan nodes and silent active flows |

Outputs: PR-style `out/gtm_review_brief.md` and `out/gtm_review_checklist.csv`. Exit code 1 on blocking findings so you can gate a local check.

## 4. CI note

The GitHub token used to publish these repos may lack the `workflow` scope. Keep examples under `ci/audit-workflows.yml`, not `.github/workflows/`, until that scope is added.
