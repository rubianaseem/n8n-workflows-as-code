#!/usr/bin/env python3
"""
GTM Workflow Review Agent
-------------------------
Reviews an n8n workflow (or a proposed diff against workflows/) for GTM risk:
hard-coded secrets, missing error branches, hard-coded emails, unsafe CRM
writes (lifecycle/owner jumps), orphan nodes, and active flows without an
error workflow. Writes a PR-style review brief and a checklist CSV.

Reuses cleaning / secret / audit helpers from n8n_versioner.py. Runs with no
API key; Claude only sharpens the review comments if ANTHROPIC_API_KEY is set.

Usage:
  python gtm_workflow_review.py
  python gtm_workflow_review.py --proposed sample_review/inbound-lead-routing.proposed.json
  python gtm_workflow_review.py --baseline workflows/inbound-lead-routing.json \\
      --proposed sample_review/inbound-lead-routing.proposed.json --output out/
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import n8n_versioner as nv

HERE = Path(__file__).resolve().parent
DEFAULT_BASELINE = HERE / "workflows" / "inbound-lead-routing.json"
DEFAULT_PROPOSED = HERE / "sample_review" / "inbound-lead-routing.proposed.json"
DEFAULT_OUTPUT = HERE / "out"
DEFAULT_MODEL = "claude-sonnet-5-5"

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
CRM_WRITE_TYPES = re.compile(r"(?i)hubspot|salesforce|pipedrive|close\.com|attio")
LIFECYCLE_JUMP = re.compile(r"(?i)lifecyclestage|lifecycle_stage|lead.?status")
OWNER_HARDCODE = re.compile(r"(?i)ownerid|hubspot_owner_id|owner_id")
UNSAFE_LIFECYCLE = re.compile(r"(?i)\b(customer|evangelist|opportunity)\b")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ and val:
            os.environ[key] = val


def gtm_checks(wf: dict) -> list[dict]:
    """Return checklist rows: severity, category, node, detail, recommendation."""
    rows: list[dict] = []
    # Reuse versioner audit
    for level, msg in nv.audit_workflow(wf):
        sev = "block" if level == "BLOCK" else "warn"
        rows.append({
            "severity": sev,
            "category": "secrets_or_hygiene" if "hard-coded" in msg or "secret" in msg or "pinned" in msg else "structure",
            "node": "",
            "detail": msg,
            "recommendation": "Fix before merge" if sev == "block" else "Address or document before production",
        })

    for node in wf.get("nodes", []):
        name = node.get("name", "")
        ntype = node.get("type", "")
        params = node.get("parameters", {}) or {}
        blob = json.dumps(params)

        # Hard-coded emails (routing risk)
        for email in EMAIL_RE.findall(blob):
            if email.endswith(".n8n.io") or "example.com" in email and "acme.example" not in email:
                continue
            rows.append({
                "severity": "warn",
                "category": "hardcoded_email",
                "node": name,
                "detail": f"Hard-coded email '{email}' in node parameters",
                "recommendation": "Move recipients to an n8n credential, env var, or HubSpot owner lookup",
            })

        # Unsafe CRM writes
        if CRM_WRITE_TYPES.search(ntype) or CRM_WRITE_TYPES.search(name):
            op = str(params.get("operation", "")).lower()
            if op in {"update", "upsert", "create"} or LIFECYCLE_JUMP.search(blob):
                if UNSAFE_LIFECYCLE.search(blob) and LIFECYCLE_JUMP.search(blob):
                    rows.append({
                        "severity": "block",
                        "category": "unsafe_crm_write",
                        "node": name,
                        "detail": "CRM node may force a late lifecycle stage (customer/opportunity) from automation",
                        "recommendation": "Restrict automation to early stages; require human approval for customer/opportunity jumps",
                    })
                if OWNER_HARDCODE.search(blob) and re.search(r"\d{3,}", blob):
                    rows.append({
                        "severity": "warn",
                        "category": "hardcoded_owner",
                        "node": name,
                        "detail": "Hard-coded owner id in CRM write",
                        "recommendation": "Use round-robin / territory rules, not a fixed owner id in the workflow JSON",
                    })
                if not node.get("continueOnFail") and op in {"update", "upsert", "create"}:
                    rows.append({
                        "severity": "warn",
                        "category": "missing_error_branch",
                        "node": name,
                        "detail": "CRM write node has no continue-on-fail / error branch",
                        "recommendation": "Add error handling so a HubSpot 429 does not leave half-updated records silently",
                    })

        # Code node without validation
        if "code" in ntype.lower():
            js = params.get("jsCode") or params.get("pythonCode") or ""
            if js and "try" not in js and "$json" in js:
                rows.append({
                    "severity": "info",
                    "category": "code_hygiene",
                    "node": name,
                    "detail": "Code node reads $json without an obvious try/guard",
                    "recommendation": "Validate required keys before mutating CRM fields",
                })

    # Active + no error workflow already covered by audit; ensure category GTM label
    return rows


def dedupe(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        key = (r["severity"], r["category"], r["node"], r["detail"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def get_client():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        return anthropic.Anthropic()
    except Exception as exc:  # noqa: BLE001
        print(f"  ! Could not init Anthropic client ({exc.__class__.__name__}); using rules only.")
        return None


def template_brief(name: str, baseline_name: str | None, rows: list[dict], diff_text: str) -> str:
    blocks = [r for r in rows if r["severity"] == "block"]
    warns = [r for r in rows if r["severity"] == "warn"]
    verdict = "REQUEST CHANGES" if blocks else ("COMMENT" if warns else "APPROVE")
    lines = [
        f"## GTM workflow review: {name}",
        "",
        f"**Verdict:** {verdict}",
        f"**Baseline:** {baseline_name or 'n/a (proposed file only)'}",
        f"**Findings:** {len(blocks)} block, {len(warns)} warn, {len(rows) - len(blocks) - len(warns)} info",
        "",
        "### Why this matters for GTM",
        "",
        "Inbound routing, event-lead cleanup, and closed-won handoffs write into HubSpot/Salesforce and Slack. "
        "A hard-coded token in git, a lifecycle jump to Customer, or a missing error branch is not a style issue — "
        "it is a CRM data and security incident waiting for the next export.",
        "",
        "### Blocking findings",
        "",
    ]
    if blocks:
        for r in blocks:
            node = f" (`{r['node']}`)" if r["node"] else ""
            lines.append(f"- **{r['category']}**{node}: {r['detail']} — {r['recommendation']}")
    else:
        lines.append("- None.")
    lines += ["", "### Warnings", ""]
    if warns:
        for r in warns[:12]:
            node = f" (`{r['node']}`)" if r["node"] else ""
            lines.append(f"- **{r['category']}**{node}: {r['detail']}")
    else:
        lines.append("- None.")
    if diff_text.strip():
        lines += ["", "### Diff summary (from n8n_versioner)", "", "```text", diff_text.strip()[:2500], "```"]
    lines += [
        "",
        "### Checklist before merge",
        "",
        "1. No secrets in node parameters (credentials only).",
        "2. Error workflow set on every active GTM flow.",
        "3. No automation writing Customer/Opportunity lifecycle without a human gate.",
        "4. Recipients and owners come from CRM fields or env, not hard-coded emails.",
        "5. `python n8n_versioner.py sync` is clean after this change.",
        "",
        f"_Review generated {date.today().isoformat()}. Nothing was written to n8n._",
        "",
    ]
    return "\n".join(lines)


def llm_polish(client, model: str, brief: str) -> str | None:
    prompt = (
        "Polish this GTM n8n PR review for a RevOps engineer. Keep the verdict, all findings, "
        "and checklist. No emojis. Keep it under 400 words.\n\n" + brief
    )
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
        return "\n".join(parts).strip() or None
    except Exception as exc:  # noqa: BLE001
        print(f"  ! Claude polish failed ({exc.__class__.__name__}); using template review.")
        return None


def write_outputs(brief: str, rows: list[dict], out_dir: Path, name: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    brief_path = out_dir / "gtm_review_brief.md"
    checklist = out_dir / "gtm_review_checklist.csv"
    brief_path.write_text(brief)
    with checklist.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["severity", "category", "node", "detail", "recommendation", "workflow"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "workflow": name})
    return {"brief": brief_path, "checklist": checklist}


def main() -> None:
    load_dotenv(HERE / ".env")
    p = argparse.ArgumentParser(description="GTM risk review for an n8n workflow change.")
    p.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="committed workflow JSON")
    p.add_argument("--proposed", type=Path, default=DEFAULT_PROPOSED, help="proposed workflow JSON")
    p.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--no-llm", action="store_true")
    args = p.parse_args()

    if not args.proposed.exists():
        sys.exit(f"Proposed workflow not found: {args.proposed}")

    proposed = nv.load_json(args.proposed)
    # Accept raw export or already-cleaned
    if "nodes" not in proposed:
        sys.exit("Proposed file does not look like an n8n workflow JSON (missing nodes).")

    baseline = nv.load_json(args.baseline) if args.baseline.exists() else None
    diff_text = ""
    if baseline is not None:
        d = nv.diff_workflow(baseline, proposed)
        diff_text = nv.rule_summary(proposed.get("name", args.proposed.name), d)

    rows = dedupe(gtm_checks(proposed))
    client = None if args.no_llm else get_client()
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)
    mode = f"Claude ({model})" if client else "built-in rules (no API key)"

    name = proposed.get("name") or args.proposed.name
    brief = template_brief(name, args.baseline.name if baseline else None, rows, diff_text)
    if client:
        brief = llm_polish(client, model, brief) or brief

    bar = "=" * 76
    print(bar)
    print(f" GTM WORKFLOW REVIEW  |  {name}  |  {mode}")
    print(bar)
    blocks = sum(1 for r in rows if r["severity"] == "block")
    warns = sum(1 for r in rows if r["severity"] == "warn")
    print(f"Findings: {blocks} block, {warns} warn, {len(rows) - blocks - warns} info")
    for r in rows:
        node = f" [{r['node']}]" if r["node"] else ""
        print(f"  {r['severity'].upper():<5} {r['category']:<22}{node} {r['detail'][:100]}")
    if diff_text:
        print("\nDiff summary:")
        print(diff_text)

    files = write_outputs(brief, rows, args.output, name)
    print(f"\n{bar}\n FILES (nothing was written to n8n)")
    for label, path in files.items():
        try:
            shown = path.relative_to(Path.cwd())
        except ValueError:
            shown = path
        print(f"  {label:<10} ./{shown}")
    print(bar)
    print("\n" + brief.split("### Checklist")[0][:1200])

    # Exit 1 on blocking findings so it can gate a PR locally
    sys.exit(1 if blocks else 0)


if __name__ == "__main__":
    main()
