# Walk through it line by line: n8n Workflows as Code

The code explained step by step, so you can learn it rather than just run it. Back to the [README](../README.md).

The whole tool is one file, [`n8n_versioner.py`](../n8n_versioner.py). These are the parts worth reading first.

**1. What an n8n workflow file is.** An export is JSON with two main parts: `nodes` (each step, with its `type` like `n8n-nodes-base.hubspot` and its `parameters`) and `connections` (which node's output goes into which node). Everything else is metadata.

**2. Removing noise (`VOLATILE_TOP_LEVEL` and `clean_workflow`).**

```python
VOLATILE_TOP_LEVEL = {"updatedAt", "createdAt", "versionId", "meta", "triggerCount", ...}
wf = {k: v for k, v in wf.items() if k not in VOLATILE_TOP_LEVEL}
```

n8n changes `versionId` and `updatedAt` every time you hit save, even if nothing else changed. If those stay in the file, every commit looks like a change. The dictionary comprehension keeps every key *except* those. Then `sorted(..., key=lambda n: n.get("name"))` puts nodes in name order and `json.dumps(..., indent=2, sort_keys=True)` writes one setting per line, so Git shows a one-line change as one line.

**3. Finding secrets (`SECRET_PATTERNS`, `find_secret`, `redact`).**

```python
(r"\bpat-(na1|eu1)-[0-9a-f-]{20,}", "HubSpot private app token"),
(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}", "Bearer token typed into a header"),
```

Each line is a regular expression (a text pattern) and a label. `redact()` walks every value in every node's parameters. It's *recursive*: if it meets a dictionary or a list it calls itself on each item, and when it reaches a plain string it checks the patterns and swaps any match for `__REDACTED_SECRET__`. Credentials stored properly in n8n only appear as `{"id": "7", "name": "HubSpot (private app)"}`, so they're untouched.

**4. Reading the change (`flatten` and `diff_workflow`).**

```python
fo, fn = flatten(old_node["parameters"]), flatten(new_node["parameters"])
for key in sorted(set(fo) | set(fn)):
    if fo.get(key) != fn.get(key): ...
```

`flatten` turns nested settings into one level, so `{"rules": {"values": [{...: 200}]}}` becomes `rules.values.1....rightValue: 200`. Comparing two flat dictionaries is then just "for every key in either, is the value different?" `set(fo) | set(fn)` means *all keys in either version*, which is how added and removed settings are caught too. Nodes are matched by `id`, so a renamed node shows as a rename, not a delete plus an add.

**5. Rewiring (`edges`).** Each connection becomes a tuple `(from_node, output_number, to_node)`. Put old and new into sets and `new - old` is every link added, `old - new` every link removed.

**6. Claude, only if you want it (`llm_summary`).** If `ANTHROPIC_API_KEY` isn't set, it returns `None` and the rule-based summary is used. If it is set, the detailed diff is sent to Claude with an instruction to explain the behaviour change for a sales ops reader and not invent anything. Any error falls back to the rules.

**7. Making CI fail (`audit` return value).** `audit()` returns `1` if there's a blocking issue, and `sys.exit(1)` makes the command "fail". That's all GitHub Actions needs: [`ci/audit-workflows.yml`](../ci/audit-workflows.yml), once moved into `.github/workflows/`, runs the audit on every push and shows a red cross if it fails.
