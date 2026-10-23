# Details: n8n Workflows as Code

Everything that used to sit in the main README, kept here so the README stays short. Back to the [README](../README.md).

## Background

I build a lot of GTM automation in n8n: lead routing, event list clean-up, deal handoffs. n8n keeps a version history inside each workflow, but that history lives in n8n, not somewhere the rest of my GTM code can sit next to it. The built-in Git sync is on the Business and Enterprise plans. Everyone else downloads a JSON file now and then and drops it in a folder.

This repo is my answer to that. It's a small Python tool plus a GitHub repo layout that turns raw n8n exports into clean, reviewable files, writes a changelog of what changed ("Round robin owner now has three AEs in Mid-market, company size threshold 200 → 250"), and blocks commits that contain a hard-coded API key or pinned test data. It's item 1 on my GTM Engineer skills roadmap: get my automations into Git properly, so everything I build after this has a home.

## Where each step runs (full version)

If you can create a repo but aren't sure where you actually *run* this, here's the whole flow in order:

1. **GitHub** is where the code and your workflow files live. Copy it to your laptop with `git clone https://github.com/rubianaseem/n8n-workflows-as-code.git`, or click **Code → Download ZIP**. Later you'll push your own workflow files back here (or to your own copy of this repo).
2. **n8n** is where your workflows actually run. Nothing here changes them. You either download each workflow from n8n (**⋯ menu → Download** on the workflow) into the `exports/` folder, or let the script fetch them for you with an n8n API key.
3. **Terminal** (Mac Terminal, or the terminal inside Cursor) is where you run `python n8n_versioner.py sync`. It reads the exports, shows what changed, cleans the files, checks them for secrets, and updates `workflows/`, `WORKFLOWS.md` and `CHANGELOG.md` on your computer.
4. **Claude is optional.** With no API key the change summary comes from built-in rules. If you add an Anthropic key to `.env`, Claude writes a short plain-English summary of the change for your changelog. It still runs in the terminal; you don't open the Claude app.
5. **You, then Git.** Read the summary, check `git diff`, then commit and push. If you switch on the included GitHub check (one file to move, see [SETUP.md](../SETUP.md#5-the-github-check)), GitHub re-runs the secret audit on every push, so a key that slips through gets flagged there too.

**This tool never writes to n8n.** It only reads exports (or reads from the n8n API) and writes files in this folder. Restoring an old version is still a manual import in n8n, on purpose.

## Full feature list

- **One command sync:** `python n8n_versioner.py sync` pulls exports, shows what changed, cleans, audits, and updates the inventory and changelog
- **Diffs a human can read:** nodes added, removed and renamed; the exact setting that changed (`200 → 250`); code lines added in Code nodes; and how the flow was rewired, instead of a 400-line JSON diff
- **Clean, stable files:** strips the fields n8n changes on every save (`versionId`, `updatedAt`, instance IDs), sorts keys and nodes, and pretty-prints, so `git diff` only shows real changes
- **Secret guard:** finds API keys typed straight into nodes (HubSpot private app tokens, Slack tokens, Bearer headers, Stripe-style `sk_live_` keys, GitHub and AWS keys), redacts them before they're written, and tells you to move them into an n8n credential and rotate them
- **No customer data in Git:** removes pinned test data, which often holds real contact records from a test run
- **Hygiene checks:** disabled nodes left lying around, nodes not connected to anything, and live workflows with no error workflow (so failures are silent)
- **Inventory page:** `WORKFLOWS.md` lists every workflow, its trigger, the systems it touches and its tags, so a new teammate can see your automation estate in one table
- **Matches workflows by ID:** rename a workflow in n8n and its file keeps its history instead of a duplicate appearing
- **GitHub Actions check** included (`ci/audit-workflows.yml`), so the audit can run on every push and pull request
- **Works with no API key and no n8n connection.** Sample exports are included, and Claude is an upgrade, not a requirement

## The pain point: all quotes and sources

People who come to n8n from code ask the same question, and the answers in the threads are mostly "download the JSON" or "upgrade":

- *"As far as I can tell there is no way to use git in conjunction with n8n other than to occasionally download a json "blueprint" of your workflow and keep a copy of it in a git repo. Not ideal obviously."* ([r/n8n: Version control for n8n?](https://www.reddit.com/r/n8n/comments/1lr56ri/version_control_for_n8n/))
- *"There a few github backup workflows that will pull your workflow json from the internal API and back it up to a repo. Otherwise go enterprise for proper solution."* (a reply in the same thread)
- *"So I'm new to N8N but I can code and I usually use git for version control while I code and I was wondering if there is a way to do it in N8N."* ([r/n8n: So how do i do version control in N8N? like git.](https://www.reddit.com/r/n8n/comments/1k6jhfe/so_how_do_i_do_version_control_in_n8n_like_git/))
- n8n's own docs say the built-in Git source control is *"Available on Business and Enterprise plans"*, and that *"n8n can't detect conflicts on workflows."* ([n8n docs: Use source control and environments](https://docs.n8n.io/administer/use-source-control-and-environments), [Push and pull changes](https://docs.n8n.io/administer/use-source-control-and-environments/push-and-pull-changes))

Backing up the JSON is the easy part, and there are good community backup workflows for it. What I wanted on top was the part a RevOps team cares about: *what did this change do to routing*, and *did someone just commit our HubSpot token*.

## Quick start and all commands

```bash
git clone https://github.com/rubianaseem/n8n-workflows-as-code.git
cd n8n-workflows-as-code
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# See it work on the sample exports (no keys, no n8n needed)
python n8n_versioner.py sync
git diff --stat
```

`workflows/` holds three sample GTM workflows as they were "last committed". `sample_exports/` holds what you'd download from n8n today: one workflow edited, one with a new step that has an API key pasted into it, and a brand-new error-alert workflow. Running `sync` shows you all of that.

The individual commands, if you want them one at a time:

| Command | What it does |
|---|---|
| `python n8n_versioner.py pull` | Fetch workflows from n8n (if `N8N_BASE_URL` + `N8N_API_KEY` are set) into `exports/`, otherwise use `sample_exports/` |
| `python n8n_versioner.py diff exports` | Plain-English list of what changed versus `workflows/` |
| `python n8n_versioner.py audit exports` | Secrets, pinned data, disabled/orphan nodes, missing error workflow. Exit code 1 if anything is blocking |
| `python n8n_versioner.py clean exports` | Write clean, diff-friendly copies into `workflows/` |
| `python n8n_versioner.py inventory` | Rebuild `WORKFLOWS.md` |
| `python n8n_versioner.py sync` | All of the above, plus a `CHANGELOG.md` entry |

## Full example output

From `python n8n_versioner.py sync` on the sample exports, with no API key:

```text
No N8N_BASE_URL/N8N_API_KEY set and nothing in exports/, so using the sample exports in sample_exports/ (mock mode).

=== What changed ===
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

=== Audit of the incoming exports (before cleaning) ===
Auditing sample_exports/ …
WARN Closed-won handoff to CS (Closed-won handoff to CS.json, 5 nodes)
     WARN: active workflow has no error workflow set, so failures are silent. Set Settings > Error workflow in n8n.
OK Error alerts (Error alerts.json, 2 nodes)
OK Event lead cleanup (Event lead cleanup.json, 6 nodes)
BLOCKED Inbound lead routing (Inbound lead routing.json, 10 nodes)
     BLOCK: Bearer token typed into a header hard-coded in node 'Enrich company domain' (headerParameters.parameters.0.value). Move it into an n8n credential and rotate the key.
     WARN: node 'Old Slack DM (unused)' is disabled. Delete it or note why it's kept.
     BLOCK: pinned test data on HubSpot: new form submission. It can hold real customer records; unpin it or run `clean` before committing.

2 blocking issue(s), 2 warning(s).

=== Clean + save ===
  SECRET redacted a hard-coded secret in Inbound lead routing: Enrich company domain (headerParameters.parameters.0.value)
Cleaned 4 workflows into workflows/ (volatile fields, pinned data and secrets removed, keys sorted).

=== Audit of what will be committed ===
Auditing workflows/ …
WARN Closed-won handoff to CS (closed-won-handoff.json, 5 nodes)
     WARN: active workflow has no error workflow set, so failures are silent. Set Settings > Error workflow in n8n.
OK Error alerts (error-alerts.json, 2 nodes)
OK Event lead cleanup (event-lead-cleanup.json, 6 nodes)
WARN Inbound lead routing (inbound-lead-routing.json, 10 nodes)
     WARN: a secret was redacted from node 'Enrich company domain' (headerParameters.parameters.0.value). Store it as an n8n credential, rotate the old key, then re-export.
     WARN: node 'Old Slack DM (unused)' is disabled. Delete it or note why it's kept.

0 blocking issue(s), 3 warning(s).
Wrote WORKFLOWS.md (4 workflows).
Added an entry to CHANGELOG.md.

Next: review with `git diff`, then `git add -A && git commit -m "Sync n8n workflows" && git push`.
```

Notice the order: the incoming exports had **2 blocking issues** (an API token typed straight into the new enrichment step's header, and a pinned test contact). After `clean`, the key is replaced with `__REDACTED_SECRET__` and the pinned data is gone, so what lands in Git has **0 blocking issues**, and the warning tells you to set up a proper credential and rotate the key. The token in the sample is fake.

## Cost

- **No API key:** free. Everything runs locally.
- **With Claude:** one short request per `sync` that finds changes, roughly a couple of thousand tokens in and a few hundred out. Check current pricing on [Anthropic's pricing page](https://www.anthropic.com/pricing); for a few syncs a week it's pennies.
- **n8n API:** no extra cost from this tool, but check your n8n plan includes API access.

## Swap the stack

| This repo uses | Swap for | What changes |
|---|---|---|
| n8n | Make, Zapier, Workato | Exports are different JSON shapes. Change `clean_workflow` and `edges`; the secret scan and changelog work as-is |
| GitHub + GitHub Actions | GitLab CI, Bitbucket Pipelines | Copy the audit step into their pipeline file |
| Manual download or n8n API | A scheduled n8n workflow that exports to a folder | Point `clean` at that folder |
| Claude | Any LLM | Replace the body of `llm_summary` |
| `sync` by hand | A Git pre-commit hook | Run `python n8n_versioner.py audit workflows` in `.git/hooks/pre-commit` |

## Customise for your stack

- **Add your own secret patterns** (Apollo, ZoomInfo, Clay webhooks, an internal API) to `SECRET_PATTERNS`. One line each: pattern and label.
- **Make warnings blocking:** if every live workflow *must* have an error workflow, change that `("WARN", ...)` to `("BLOCK", ...)` in `audit_workflow`.
- **Organise by team:** put workflows in `workflows/revops/`, `workflows/marketing-ops/` and point `audit` at each folder.
- **Use real owners:** tag workflows in n8n with an owner name and they'll show up in `WORKFLOWS.md`.

## How this runs today (and what production would add)

**Today:** it runs on my laptop against sample exports that I wrote to look like real GTM workflows (routing, event clean-up, closed-won handoff, error alerts). The pull from the n8n API is written against n8n's public API (`GET /api/v1/workflows` with an `X-N8N-API-KEY` header), and is mocked by `sample_exports/` when no key is set. The secret patterns cover the common formats, not every one; treat it as a safety net, not a guarantee.

**Production would add:**
- A scheduled run (a nightly GitHub Action or an n8n workflow) so syncing doesn't depend on someone remembering
- Separate dev and prod n8n instances with changes promoted in one direction only, which is also what n8n recommends for its built-in source control
- Pushing restored versions *back* into n8n through the API, with an approval step, instead of a manual import
- A proper secret scanner such as gitleaks alongside these patterns
- Credentials and variables documented as stubs (name and type only) so a new instance can be rebuilt from the repo

---

Questions or ideas? Open an issue. If you're an n8n user who doesn't have the Business plan yet, I hope this gives you most of the benefit for free.
