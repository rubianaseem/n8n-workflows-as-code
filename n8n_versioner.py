#!/usr/bin/env python3
"""
n8n-versioner: keep your n8n workflows in GitHub like real code.

Commands
  pull      Get workflow exports: from your n8n instance (if N8N_BASE_URL + N8N_API_KEY are set),
            else from files you downloaded into exports/, else from sample_exports/ (mock mode).
  clean     Turn raw n8n exports into tidy, diff-friendly files in workflows/.
  diff      Show what changed between the committed workflows/ and fresh exports, in plain English.
  audit     Check workflows for leaked secrets, pinned test data, disabled or orphan nodes
            and missing error handling. Exits 1 on blocking issues, so it works as a CI check.
  inventory Write WORKFLOWS.md: one table of every workflow, its trigger, systems and owner tags.
  sync      pull + diff + clean + audit + inventory in one go, and write CHANGELOG.md.

It never changes anything inside n8n. It only reads exports and writes files in this folder.
Claude is optional: with ANTHROPIC_API_KEY set, the change summary is written by Claude;
otherwise a rule-based summary is used.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
WORKFLOWS_DIR = ROOT / "workflows"
EXPORTS_DIR = ROOT / "exports"
SAMPLE_DIR = ROOT / "sample_exports"

# Fields n8n changes on every save or that only make sense on one instance.
# Keeping them in git creates noisy diffs that hide the real change.
VOLATILE_TOP_LEVEL = {"updatedAt", "createdAt", "versionId", "meta", "triggerCount",
                      "shared", "staticData", "isArchived", "homeProject", "scopes"}

# Patterns that look like a real secret pasted into a node instead of stored as an n8n credential.
SECRET_PATTERNS = [
    (r"\bpat-(na1|eu1)-[0-9a-f-]{20,}", "HubSpot private app token"),
    (r"\bxox[abposr]-[A-Za-z0-9-]{10,}", "Slack token"),
    (r"\bsk-ant-[A-Za-z0-9_-]{10,}", "Anthropic API key"),
    (r"\bsk_(live|test)_[A-Za-z0-9]{10,}", "Live/test secret key"),
    (r"\bsk-[A-Za-z0-9]{20,}", "OpenAI-style API key"),
    (r"\bgh[pousr]_[A-Za-z0-9]{20,}", "GitHub token"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key"),
    (r"(?i)bearer\s+[A-Za-z0-9._-]{20,}", "Bearer token typed into a header"),
    (r"(?i)hapikey=[A-Za-z0-9-]{10,}", "Old HubSpot API key in a URL"),
]

REDACTED = "__REDACTED_SECRET__"


def find_secret(text: str):
    for pat, label in SECRET_PATTERNS:
        if re.search(pat, text):
            return label
    return None


def redact(obj, found: list, path="", node=""):
    """Replace anything that looks like a secret so it can never be committed."""
    if isinstance(obj, dict):
        return {k: redact(v, found, f"{path}.{k}" if path else k, node) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v, found, f"{path}.{i}", node) for i, v in enumerate(obj)]
    if isinstance(obj, str) and find_secret(obj):
        found.append(f"{node} ({path})")
        out = obj
        for pat, _ in SECRET_PATTERNS:
            out = re.sub(pat, REDACTED, out)
        return out
    return obj


TRIGGER_HINT = re.compile(r"(?i)trigger|webhook")


# ---------- helpers ----------

def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workflow"


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def read_dir(folder: Path) -> dict:
    """Return {workflow_id_or_name: (path, workflow)} for every .json file in a folder."""
    out = {}
    for p in sorted(folder.glob("*.json")):
        try:
            wf = load_json(p)
        except json.JSONDecodeError as e:
            print(f"  ! Skipping {p.name}: not valid JSON ({e})")
            continue
        if "nodes" not in wf:
            print(f"  ! Skipping {p.name}: doesn't look like an n8n workflow (no 'nodes')")
            continue
        out[wf.get("id") or wf.get("name") or p.stem] = (p, wf)
    return out


def flatten(obj, prefix=""):
    """Turn nested parameters into {'a.b.0.c': value} so changes can be listed one by one."""
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            items.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            items.update(flatten(v, f"{prefix}.{i}"))
    else:
        items[prefix] = obj
    return items


def short(v, n=70):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def node_kind(t: str) -> str:
    return t.split(".")[-1]


# ---------- pull ----------

def pull(source: str) -> Path:
    base, key = os.getenv("N8N_BASE_URL"), os.getenv("N8N_API_KEY")
    if source == "api" or (source == "auto" and base and key):
        if not (base and key):
            sys.exit("N8N_BASE_URL and N8N_API_KEY must be set to pull from n8n. See SETUP.md.")
        import requests
        EXPORTS_DIR.mkdir(exist_ok=True)
        url, cursor, count = base.rstrip("/") + "/api/v1/workflows", None, 0
        while True:
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            r = requests.get(url, headers={"X-N8N-API-KEY": key, "accept": "application/json"},
                             params=params, timeout=30)
            if r.status_code == 401:
                sys.exit("n8n said 401 Unauthorized. Check N8N_API_KEY (Settings > n8n API in n8n).")
            r.raise_for_status()
            body = r.json()
            for wf in body.get("data", []):
                write_json(EXPORTS_DIR / f"{slugify(wf['name'])}.json", wf)
                count += 1
            cursor = body.get("nextCursor")
            if not cursor:
                break
        print(f"Pulled {count} workflows from {base} into {EXPORTS_DIR.name}/")
        return EXPORTS_DIR
    if source == "auto" and EXPORTS_DIR.exists() and any(EXPORTS_DIR.glob("*.json")):
        print(f"No n8n API key set, so using the files you downloaded into {EXPORTS_DIR.name}/.")
        return EXPORTS_DIR
    print(f"No N8N_BASE_URL/N8N_API_KEY set and nothing in {EXPORTS_DIR.name}/, "
          f"so using the sample exports in {SAMPLE_DIR.name}/ (mock mode).")
    return SAMPLE_DIR


# ---------- clean ----------

def clean_workflow(wf: dict, found: list | None = None) -> dict:
    found = [] if found is None else found
    wf = {k: v for k, v in wf.items() if k not in VOLATILE_TOP_LEVEL}
    wf["nodes"] = [{**n, "parameters": redact(n.get("parameters", {}), found, node=n.get("name", ""))}
                   for n in wf.get("nodes", [])]
    if wf.get("pinData"):
        wf["pinData"] = {}  # pinned test data often holds real customer records
    wf["nodes"] = sorted(wf.get("nodes", []), key=lambda n: n.get("name", ""))
    if "tags" in wf:
        wf["tags"] = sorted([{"name": t["name"]} if isinstance(t, dict) else {"name": t}
                             for t in wf["tags"]], key=lambda t: t["name"])
    return wf


def clean(src: Path, dest: Path = WORKFLOWS_DIR) -> list:
    dest.mkdir(exist_ok=True)
    existing = read_dir(dest)
    written = []
    for wid, (path, wf) in read_dir(src).items():
        target = existing[wid][0] if wid in existing else dest / f"{slugify(wf['name'])}.json"
        found = []
        write_json(target, clean_workflow(wf, found))
        written.append(target)
        for f in found:
            print(f"  SECRET redacted a hard-coded secret in {wf['name']}: {f}")
    print(f"Cleaned {len(written)} workflows into {dest.name}/ (volatile fields, pinned data and secrets removed, keys sorted).")
    return written


# ---------- diff ----------

def diff_workflow(old: dict, new: dict) -> dict:
    o = {n["name"]: n for n in old.get("nodes", [])}
    n = {x["name"]: x for x in new.get("nodes", [])}
    o_by_id = {v.get("id"): k for k, v in o.items()}
    renamed = {}
    for name, node in n.items():
        old_name = o_by_id.get(node.get("id"))
        if old_name and old_name != name and old_name not in n:
            renamed[old_name] = name
    added = [k for k in n if k not in o and k not in renamed.values()]
    removed = [k for k in o if k not in n and k not in renamed]
    changed = {}
    for old_name, new_node in [(k, n[k]) for k in n if k in o] + [(a, n[b]) for a, b in renamed.items()]:
        old_node = o[old_name]
        lines = []
        fo, fn = flatten(old_node.get("parameters", {})), flatten(new_node.get("parameters", {}))
        for key in sorted(set(fo) | set(fn)):
            if fo.get(key) != fn.get(key):
                if key.endswith("jsCode") or key.endswith("pythonCode"):
                    lines.append(code_change(fo.get(key, ""), fn.get(key, "")))
                else:
                    lines.append(f"`{key}`: {short(fo.get(key, '(none)'))} → {short(fn.get(key, '(none)'))}")
        if old_node.get("disabled") != new_node.get("disabled"):
            lines.append("node was " + ("disabled" if new_node.get("disabled") else "re-enabled"))
        if old_node.get("credentials") != new_node.get("credentials"):
            lines.append("credential changed")
        if lines:
            changed[new_node["name"]] = lines
    oc, nc = edges(old), edges(new)
    settings = []
    if old.get("active") != new.get("active"):
        settings.append("workflow is now " + ("ACTIVE" if new.get("active") else "inactive"))
    if old.get("settings", {}).get("errorWorkflow") != new.get("settings", {}).get("errorWorkflow"):
        settings.append(f"error workflow: {old.get('settings', {}).get('errorWorkflow')} → {new.get('settings', {}).get('errorWorkflow')}")
    return {"added": added, "removed": removed, "renamed": renamed, "changed": changed,
            "links_added": sorted(nc - oc), "links_removed": sorted(oc - nc), "settings": settings}


def code_change(a: str, b: str) -> str:
    al, bl = set(str(a).splitlines()), set(str(b).splitlines())
    plus = [l.strip() for l in str(b).splitlines() if l not in al]
    minus = [l.strip() for l in str(a).splitlines() if l not in bl]
    parts = []
    if minus:
        parts.append("removed line(s): " + "; ".join(short(m, 120) for m in minus[:3]))
    if plus:
        parts.append("added line(s): " + "; ".join(short(p, 120) for p in plus[:3]))
    return "code changed, " + ", ".join(parts) if parts else "code reformatted"


def edges(wf: dict) -> set:
    out = set()
    for src, kinds in wf.get("connections", {}).items():
        for outputs in kinds.values():
            for i, targets in enumerate(outputs or []):
                for t in targets or []:
                    out.add((src, i, t["node"]))
    return out


def is_empty(d: dict) -> bool:
    return not any(d.values())


def rule_summary(name: str, d: dict) -> str:
    bits = []
    if d["added"]:
        bits.append(f"adds {', '.join(d['added'])}")
    if d["removed"]:
        bits.append(f"removes {', '.join(d['removed'])}")
    if d["renamed"]:
        bits.append("renames " + ", ".join(f"{a} to {b}" for a, b in d["renamed"].items()))
    if d["changed"]:
        bits.append(f"edits {', '.join(d['changed'])}")
    if d["links_added"] or d["links_removed"]:
        bits.append("rewires the flow")
    return f"{name}: " + ("; ".join(bits) if bits else "no logic change") + "."


def llm_summary(text: str) -> str | None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
            max_tokens=500,
            messages=[{"role": "user", "content":
                "You are reviewing a change to n8n automation workflows for a RevOps team. "
                "Write 2-4 plain-English bullet points a non-developer sales ops lead would understand: "
                "what behaviour changes for leads, deals, owners or Slack alerts, and any risk to check before "
                "turning it on. Don't invent anything that isn't in the diff.\n\n" + text}])
        return msg.content[0].text.strip()
    except Exception as e:  # any API problem falls back to the rules
        print(f"  (Claude summary skipped: {e.__class__.__name__}; using rule-based summary)")
        return None


def diff_dirs(old_dir: Path, new_dir: Path) -> str:
    old, new = read_dir(old_dir), read_dir(new_dir)
    lines, summaries = [], []
    for wid, (path, wf) in new.items():
        nw = clean_workflow(wf)
        if wid not in old:
            lines.append(f"### NEW {nw['name']} (new workflow, {len(nw['nodes'])} nodes)")
            summaries.append(f"{nw['name']}: new workflow added.")
            continue
        d = diff_workflow(clean_workflow(old[wid][1]), nw)
        if is_empty(d):
            continue
        lines.append(f"### EDITED {nw['name']}")
        for a in d["added"]:
            node = next(x for x in nw["nodes"] if x["name"] == a)
            lines.append(f"- ADDED node **{a}** ({node_kind(node['type'])})")
        for r in d["removed"]:
            lines.append(f"- REMOVED node **{r}**")
        for a, b in d["renamed"].items():
            lines.append(f"- RENAMED **{a}** → **{b}**")
        for nname, changes in d["changed"].items():
            for c in changes:
                lines.append(f"- CHANGED **{nname}**: {c}")
        for s, i, t in d["links_added"]:
            lines.append(f"- LINK now connects {s} (output {i}) → {t}")
        for s, i, t in d["links_removed"]:
            lines.append(f"- UNLINKED no longer connects {s} (output {i}) → {t}")
        for s in d["settings"]:
            lines.append(f"- SETTING {s}")
        summaries.append(rule_summary(nw["name"], d))
    for wid, (path, wf) in old.items():
        if wid not in new:
            lines.append(f"### MISSING {wf['name']} (missing from the new export: deleted or renamed in n8n?)")
            summaries.append(f"{wf['name']}: not in the new export.")
    if not lines:
        return "No workflow changes since the last commit."
    detail = "\n".join(lines)
    ai = llm_summary(detail)
    summary = ai if ai else "\n".join(f"- {s}" for s in summaries)
    label = "Summary (written by Claude)" if ai else "Summary (rule-based)"
    return f"**{label}**\n\n{summary}\n\n**Details**\n\n{detail}"


# ---------- audit ----------

def audit_workflow(wf: dict) -> list:
    """Return a list of (level, message). level is BLOCK or WARN."""
    issues = []
    raw = json.dumps(wf.get("nodes", []))
    for node in wf.get("nodes", []):
        for key, val in flatten(node.get("parameters", {})).items():
            if not isinstance(val, str):
                continue
            if REDACTED in val:
                issues.append(("WARN", f"a secret was redacted from node '{node['name']}' ({key}). "
                                       "Store it as an n8n credential, rotate the old key, then re-export."))
                continue
            label = find_secret(val)
            if label:
                issues.append(("BLOCK", f"{label} hard-coded in node '{node['name']}' ({key}). "
                                        "Move it into an n8n credential and rotate the key."))
        if node.get("disabled"):
            issues.append(("WARN", f"node '{node['name']}' is disabled. Delete it or note why it's kept."))
    if wf.get("pinData"):
        issues.append(("BLOCK", f"pinned test data on {', '.join(wf['pinData'])}. It can hold real "
                                "customer records; unpin it or run `clean` before committing."))
    linked = {s for s, _, _ in edges(wf)} | {t for _, _, t in edges(wf)}
    for node in wf.get("nodes", []):
        if node["name"] not in linked and len(wf["nodes"]) > 1 and not node.get("disabled") \
                and "stickyNote" not in node["type"]:
            issues.append(("WARN", f"node '{node['name']}' isn't connected to anything."))
    has_trigger = any(TRIGGER_HINT.search(n["type"]) for n in wf.get("nodes", []))
    if wf.get("active") and has_trigger and "errorTrigger" not in raw \
            and not wf.get("settings", {}).get("errorWorkflow"):
        issues.append(("WARN", "active workflow has no error workflow set, so failures are silent. "
                               "Set Settings > Error workflow in n8n."))
    return issues


def audit(folder: Path) -> int:
    blocks = warns = 0
    print(f"Auditing {folder.name}/ …")
    for wid, (path, wf) in read_dir(folder).items():
        issues = audit_workflow(wf)
        status = "OK" if not issues else ("BLOCKED" if any(l == "BLOCK" for l, _ in issues) else "WARN")
        print(f"{status} {wf['name']} ({path.name}, {len(wf['nodes'])} nodes)")
        for level, msg in issues:
            print(f"     {level}: {msg}")
            blocks += level == "BLOCK"
            warns += level == "WARN"
    print(f"\n{blocks} blocking issue(s), {warns} warning(s).")
    return 1 if blocks else 0


# ---------- inventory ----------

def inventory(folder: Path = WORKFLOWS_DIR, out: Path = ROOT / "WORKFLOWS.md") -> None:
    rows = []
    for wid, (path, wf) in read_dir(folder).items():
        trig = next((n for n in wf["nodes"] if TRIGGER_HINT.search(n["type"])), None)
        systems = sorted({node_kind(n["type"]).replace("Trigger", "") for n in wf["nodes"]
                          if node_kind(n["type"]) not in {"if", "switch", "code", "set", "removeDuplicates",
                                                          "scheduleTrigger", "errorTrigger", "stickyNote"}})
        tags = ", ".join(t["name"] for t in wf.get("tags", []))
        rows.append(f"| [{wf['name']}]({folder.name}/{path.name}) | {'active' if wf.get('active') else 'off'} "
                    f"| {node_kind(trig['type']) if trig else 'manual'} | {', '.join(systems)} | {len(wf['nodes'])} | {tags} |")
    out.write_text("# Workflow inventory\n\n_Generated by `python n8n_versioner.py inventory`. Don't edit by hand._\n\n"
                   "| Workflow | Status | Trigger | Systems touched | Nodes | Tags |\n|---|---|---|---|---|---|\n"
                   + "\n".join(rows) + "\n", encoding="utf-8")
    print(f"Wrote {out.name} ({len(rows)} workflows).")


# ---------- sync ----------

def sync(source: str) -> int:
    src = pull(source)
    print("\n=== What changed ===")
    report = diff_dirs(WORKFLOWS_DIR, src)
    print(report)
    print("\n=== Audit of the incoming exports (before cleaning) ===")
    audit(src)
    print("\n=== Clean + save ===")
    clean(src)
    print("\n=== Audit of what will be committed ===")
    code = audit(WORKFLOWS_DIR)
    inventory()
    if not report.startswith("No workflow changes"):
        log = ROOT / "CHANGELOG.md"
        prev = log.read_text(encoding="utf-8") if log.exists() else "# Changelog\n"
        head, _, rest = prev.partition("\n")
        log.write_text(f"{head}\n\n## {date.today().isoformat()}\n\n{report}\n{rest}", encoding="utf-8")
        print("Added an entry to CHANGELOG.md.")
    print("\nNext: review with `git diff`, then `git add -A && git commit -m \"Sync n8n workflows\" && git push`.")
    return code


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    p = argparse.ArgumentParser(description="Version your n8n workflows in git.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("pull"); s.add_argument("--source", choices=["auto", "api", "sample"], default="auto")
    s = sub.add_parser("clean"); s.add_argument("src", nargs="?", default=str(SAMPLE_DIR))
    s = sub.add_parser("diff"); s.add_argument("new", nargs="?", default=str(SAMPLE_DIR))
    s.add_argument("--old", default=str(WORKFLOWS_DIR))
    s = sub.add_parser("audit"); s.add_argument("folder", nargs="?", default=str(WORKFLOWS_DIR))
    sub.add_parser("inventory")
    s = sub.add_parser("sync"); s.add_argument("--source", choices=["auto", "api", "sample"], default="auto")
    a = p.parse_args()
    if a.cmd == "pull":
        pull(a.source)
    elif a.cmd == "clean":
        clean(Path(a.src))
    elif a.cmd == "diff":
        print(diff_dirs(Path(a.old), Path(a.new)))
    elif a.cmd == "audit":
        sys.exit(audit(Path(a.folder)))
    elif a.cmd == "inventory":
        inventory()
    elif a.cmd == "sync":
        sys.exit(sync(a.source))


if __name__ == "__main__":
    main()
