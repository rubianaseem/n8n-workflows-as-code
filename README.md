# n8n Workflows as Code

**Keep every n8n workflow in GitHub, see exactly what changed in plain English, and stop API keys and customer data from sneaking into your repo.**

> Built by Rubia Naseem, GTM Engineer (12+ yrs CRM/RevOps, HubSpot & Salesforce).

---

## The pain point

I build a lot of GTM automation in n8n. Its version history lives inside n8n, the built-in Git sync is on the Business and Enterprise plans, and everyone else downloads a JSON file now and then. Backing up the JSON is the easy part. What I wanted was what a RevOps team cares about: *what did this change do to routing*, and *did someone just commit our HubSpot token*.

- *"As far as I can tell there is no way to use git in conjunction with n8n other than to occasionally download a json "blueprint" of your workflow and keep a copy of it in a git repo. Not ideal obviously."* ([r/n8n: Version control for n8n?](https://www.reddit.com/r/n8n/comments/1lr56ri/version_control_for_n8n/))
- *"So I'm new to N8N but I can code and I usually use git for version control while I code and I was wondering if there is a way to do it in N8N."* ([r/n8n: So how do i do version control in N8N? like git.](https://www.reddit.com/r/n8n/comments/1k6jhfe/so_how_do_i_do_version_control_in_n8n_like_git/))

---

## What it does

- **One command sync:** `python n8n_versioner.py sync` pulls exports, shows what changed, cleans, audits, and updates the inventory and changelog
- **Diffs a human can read:** nodes added, removed and renamed, the exact setting that changed (`200 → 250`), and how the flow was rewired
- **Clean, stable files:** strips the fields n8n changes on every save, so `git diff` only shows real changes
- **Secret guard:** finds API keys typed straight into nodes, redacts them, and removes pinned test data that can hold real contacts
- **Inventory page:** `WORKFLOWS.md` lists every workflow, its trigger, the systems it touches and its tags
- **Works with no API key and no n8n connection:** sample exports are included, and Claude only writes the summary if you add a key

---

## Where each step runs

1. **GitHub** holds the code and your workflow files. Clone it or click **Code → Download ZIP**.
2. **n8n** is where your workflows run. Nothing here changes them; you download exports into `exports/`, or let the script fetch them with an n8n API key.
3. **Terminal** is where you run `python n8n_versioner.py sync`. It cleans, checks and updates the files on your computer.
4. **Claude is optional.** With an Anthropic key it writes the plain-English change summary; without one, built-in rules do. It all stays in the terminal.
5. **You, then Git.** Read the summary, check `git diff`, then commit and push.

**This tool never writes to n8n.**

---

## Quick start

```bash
git clone https://github.com/rubianaseem/n8n-workflows-as-code.git
cd n8n-workflows-as-code
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python n8n_versioner.py sync   # sample exports, no keys, no n8n needed
git diff --stat
```

---

## Example output

From `python n8n_versioner.py sync` on the sample exports, with no API key:

```text
=== What changed ===
- Inbound lead routing: adds Enrich company domain, Old Slack DM (unused); edits Round robin owner, Segment by company size; rewires the flow.
- 🔧 **Segment by company size**: `rules.values.1.conditions.conditions.0.rightValue`: 200 → 250

=== Audit of the incoming exports (before cleaning) ===
⛔ Inbound lead routing (Inbound lead routing.json, 10 nodes)
     BLOCK: Bearer token typed into a header hard-coded in node 'Enrich company domain' (headerParameters.parameters.0.value). Move it into an n8n credential and rotate the key.
2 blocking issue(s), 2 warning(s).

=== Audit of what will be committed ===
0 blocking issue(s), 3 warning(s).
```

After `clean`, the key is replaced with `__REDACTED_SECRET__` and the pinned data is gone. The token in the sample is fake.

---

## More

- [SETUP.md](SETUP.md): Claude, your real n8n workflows, switching on the GitHub check, extending it, troubleshooting
- [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md): walk through `n8n_versioner.py` line by line
- [docs/DETAILS.md](docs/DETAILS.md): all the pain-point quotes, full feature list, every command, the full example output, cost, swap the stack, customising, and how this runs today vs production
