# Changelog

## 2026-10-28

**Summary (rule-based)**

- Closed-won handoff to CS: edits Post to #cs-handoffs.
- Error alerts: new workflow added.
- Inbound lead routing: adds Enrich company domain, Old Slack DM (unused); edits Round robin owner, Segment by company size; rewires the flow.

**Details**

### EDITED Closed-won handoff to CS
- CHANGED **Post to #cs-handoffs**: `channelId.value`: #cs-handoffs → #cs-onboarding
### NEW Error alerts (new workflow, 2 nodes)
### EDITED Inbound lead routing
- ADDED node **Enrich company domain** (httpRequest)
- ADDED node **Old Slack DM (unused)** (slack)
- CHANGED **Round robin owner**: code changed, removed line(s): 'Mid-market': ['ae.sam@example.com', 'ae.lena@example.com'],, added line(s): 'Mid-market': ['ae.sam@example.com', 'ae.lena@example.com', 'ae.kofi@example.com'],
- CHANGED **Segment by company size**: `rules.values.1.conditions.conditions.0.rightValue`: 200 → 250
- LINK now connects Enrich company domain (output 0) → Is it a business email?
- LINK now connects Get contact + company (output 0) → Enrich company domain
- UNLINKED no longer connects Get contact + company (output 0) → Is it a business email?

## 2026-10-21

- First commit: Inbound lead routing, Event lead cleanup and Closed-won handoff to CS exported from n8n and cleaned.
