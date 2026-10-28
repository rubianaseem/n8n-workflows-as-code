# Setup guide

Everything here runs in a terminal (Mac Terminal, or the terminal panel in Cursor). You need Python 3.10 or newer (`python3 --version` to check) and Git.

## 1. Get the code and make a virtual environment

```bash
git clone https://github.com/rubianaseem/n8n-workflows-as-code.git
cd n8n-workflows-as-code
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

The virtual environment (`.venv`) keeps this project's packages separate from everything else on your laptop. Run `source .venv/bin/activate` again whenever you open a new terminal.

## 2. Sample run (no keys, no n8n)

```bash
python n8n_versioner.py sync
git status          # (if you cloned it) see which files changed
git diff workflows/ # the clean, readable change
```

To reset the sample and run it again: `git checkout -- workflows WORKFLOWS.md CHANGELOG.md && git clean -fd workflows`.

## 3. Optional: Claude for the change summary

```bash
cp .env.example .env
```

Open `.env` and paste your key after `ANTHROPIC_API_KEY=` (get one at [console.anthropic.com](https://console.anthropic.com/)). The next `sync` or `diff` prints **Summary (written by Claude)**. Remove the key to go back to the rule-based summary. `.env` is in `.gitignore`, so it is never committed.

## 4. Use your real n8n workflows

### Option A: download by hand (any n8n plan)

1. In n8n, open a workflow, click the **⋯** menu (top right) and choose **Download**.
2. Save the `.json` file into a folder called `exports/` inside this repo (create it the first time).
3. Repeat for each workflow you want versioned.
4. Delete the sample files the first time so only your workflows are tracked: `rm workflows/*.json sample_exports/*.json`.
5. Run `python n8n_versioner.py sync`.

`exports/` is in `.gitignore`: raw downloads can contain secrets and pinned customer data, and only the cleaned copies in `workflows/` should be committed.

### Option B: pull with the n8n API

1. In n8n go to **Settings → n8n API** and create an API key. (Check your plan includes API access.)
2. In `.env` set `N8N_BASE_URL` (for example `https://yourname.app.n8n.cloud`, or your self-hosted URL) and `N8N_API_KEY`.
3. Run `python n8n_versioner.py sync`. It calls `GET /api/v1/workflows`, follows pagination, and saves each workflow into `exports/` before cleaning.

The tool only *reads* from n8n. It never edits, activates or deletes a workflow.

### Make it your own repo

```bash
gh repo create my-n8n-workflows --private --source . --remote mine   # or create it on github.com
git add -A && git commit -m "Version my n8n workflows"
git push mine main
```

Use a **private** repo for real company workflows. Even with secrets removed, workflows describe your internal processes, owner emails and Slack channels.

## 5. The GitHub check

`ci/audit-workflows.yml` is a GitHub Actions file that runs `python n8n_versioner.py audit workflows` on GitHub whenever `workflows/` changes. It ships in `ci/` so it's easy to read; GitHub only runs it from `.github/workflows/`, so switch it on once:

```bash
mkdir -p .github/workflows
git mv ci/audit-workflows.yml .github/workflows/
git commit -m "Turn on n8n workflow audit" && git push
```

(If the push is refused with a message about `workflow` scope, your GitHub token can't change Actions files. Add the file on github.com instead: **Add file → Create new file**, name it `.github/workflows/audit-workflows.yml`, and paste the contents.)

After that you'll see a green tick or red cross next to each commit and pull request.

Optional local guard, so you can't even commit a secret:

```bash
printf '#!/bin/sh\n.venv/bin/python n8n_versioner.py audit workflows\n' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## 6. Extend it with an AI coding assistant

Open the folder in **Cursor**, **Claude Code**, **Codex CLI** or **Grok** and ask in plain words. Prompts that work well:

- "Add a secret pattern for Apollo API keys to `SECRET_PATTERNS` and add a sample node that uses one, then run `python n8n_versioner.py audit sample_exports` to prove it's caught."
- "Add a `restore` command that takes a workflow file from `workflows/` and creates it in n8n through the API, but only after I type yes."
- "Write a GitHub Action that runs `sync` with my n8n API key from repository secrets every night and opens a pull request if anything changed."
- "Explain `diff_workflow` to me line by line."

Ask it to run the script after every change, and read the diff it made before you commit.

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `command not found: python` | Use `python3`, or activate the venv first |
| `ModuleNotFoundError: requests` / `dotenv` | `source .venv/bin/activate` then `pip install -r requirements.txt` |
| `n8n said 401 Unauthorized` | The API key is wrong or was deleted. Make a new one in n8n Settings → n8n API |
| `Skipping X.json: doesn't look like an n8n workflow` | That file isn't a workflow export (maybe a credentials or project file). Remove it from `exports/` |
| Every file shows as changed on the first real sync | Expected the first time: the files are being normalised. Later syncs only show real changes |
| A workflow appears twice in `workflows/` | It was re-created in n8n with a new ID. Delete the old file once you've checked it's the same workflow |
| Claude summary skipped | The message says why (bad key, network). The rule-based summary is used instead |
| GitHub check is red | Run `python n8n_versioner.py audit workflows` locally; it prints the node and setting that tripped it |


## GTM workflow review

```bash
python gtm_workflow_review.py \
  --baseline workflows/inbound-lead-routing.json \
  --proposed sample_review/inbound-lead-routing.proposed.json \
  --output out/ --no-llm
```

Or: `python n8n_versioner.py review --no-llm`.

Blocking findings exit 1. Fix secrets and unsafe CRM writes before you commit. Claude is optional for polishing the brief.
