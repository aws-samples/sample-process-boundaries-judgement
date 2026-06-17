# Governed Reasoning POC

Schema-bounded reasoning record with adversarial validation, demonstrated on a SaaS revenue-recognition case under ASC 606.

## ⚠️ Security notice

**This is a proof-of-concept for testing and experimentation only. It is not hardened for production use.** Run it against non-sensitive data, in a non-production AWS account, and review the points below before use.

- **Case content is sent to Amazon Bedrock.** The `case_body` and `standards` fields of every case are transmitted to the configured Bedrock models for inference. Do not put confidential, regulated, or personally identifiable data in case files unless your Bedrock environment is approved for it.
- **LLM output is not authoritative.** Generated records and memos are a reasoning aid, not legal, accounting, or compliance advice. Treat conclusions as drafts that require expert human review.
- **The HTML viewer is not XSS-hardened.** `gr visualize --format html` embeds the record's (LLM-generated) content into an inline `<script>` block via `json.dumps`, which does not escape a literal `</script>` sequence. Only generate and open HTML from records you trust, and open the file locally rather than serving it. The viewer also loads Cytoscape/dagre from a public CDN (pinned with Subresource Integrity hashes), so rendering requires outbound internet access.
- **`--render-svg` shells out to the local `dot` binary.** Invocation is safe (list-form arguments, no shell, binary resolved via `shutil.which`), but it does execute a local Graphviz install.

## Setup

```
uv sync
```

Requires AWS CLI profile `east` with Bedrock model access for:
- `global.anthropic.claude-opus-4-7`
- `global.anthropic.claude-sonnet-4-6`
- `global.anthropic.claude-haiku-4-5-20251001-v1:0`

## Run

```
uv run gr run cases/example_revrec.json
```

Outputs to `records/<case-id>.json` (record) and `records/<case-id>.md` (memo).

## Visualize a record

```
uv run gr visualize records/<case-id>.json --format all --render-svg
```

Outputs:

- `<case-id>.dot` — Graphviz DOT for the full record. Color-coded by node kind (facts blue, standards purple, interpretations white, thresholds yellow diamond, alternatives gray dashed, conclusions teal bold, open questions pink dashed). Edges labeled with relationship (`supports`, `appliesTo`, `anchors`, `derivedFrom`).
- `<case-id>.svg` — Rendered DOT (only if `dot` is on PATH; install with `brew install graphviz`).
- `<case-id>.headline.mmd` — A Mermaid flowchart of just the conclusions and their direct supports. Renders inline in GitHub, Obsidian, and most Markdown viewers. Use as a memo-front-matter view.
- `<case-id>.html` — Self-contained interactive viewer (Cytoscape.js + dagre, loaded from a CDN). Hierarchical left-to-right layout, click any node for full details in a side panel, three filters (by kind, by minimum confidence, by comfort zone). Open by double-clicking the file or via `open`.

Other flags:

- `--format dot|mermaid|html|both|all` — `both` is dot+mermaid (default, preserves prior behavior); `all` adds the HTML viewer.
- `--out-dir <path>` (default: same directory as the record)

## Add your own scenario

A scenario is a single case JSON file in `cases/`. Copy `cases/example_revrec.json` as a starting point. Each file needs exactly three string fields:

| Field | Purpose |
|---|---|
| `case_id` | Unique slug; used to name the output files (`records/<case_id>.json` and `.md`). Use lowercase, no spaces. |
| `case_body` | The fact pattern / question to reason about, in prose. |
| `standards` | The governing rules, regulations, or policies the reasoning must be bounded by. Paste the relevant excerpts verbatim; cite the source and effective date so the agent anchors to them. |

Example skeleton:

```json
{
  "case_id": "my-scenario-2026-q2",
  "case_body": "Describe the situation and the question to be answered...",
  "standards": "Paste the controlling standard text here (with citations and effective dates)..."
}
```

Then run it like any other case:

```
uv run gr run cases/my-scenario-2026-q2.json
```

Tips:
- The domain is not hard-coded to revenue recognition — supply any `standards` text (a contract clause, an internal policy, a different accounting topic) and the agent will reason within those bounds.
- Generated records and memos in `records/` are gitignored; only the case files in `cases/` are tracked.

## Test

```
uv run pytest
```

## Sample output

A run on `cases/example_revrec.json` (a SaaS multi-year contract revenue recognition question under ASC 606) produced a 52-node record:

- 8 facts, 12 standard references, 8 interpretations, 3 thresholds
- 8 alternatives considered, 4 conclusions, 9 open questions
- 1 adversarial round with 11 challenges (the agent extended the record from 32 to 52 nodes after responding)

The generated memo surfaces open questions prominently before the body, with `[ref:node-id]` hyperlinks to supporting nodes throughout. Records are gitignored; commit a redacted sample under `docs/samples/` if you need to share one.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
