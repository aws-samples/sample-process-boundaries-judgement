# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Render a ReasoningRecord as Graphviz DOT, Mermaid headline, or interactive HTML.

Pure functions: take a record, return a string. No I/O, no external rendering.
"""

import json

from .schema import ReasoningRecord


_STYLE_BY_KIND = {
    "fact":           {"shape": "box",     "fillcolor": "#BFE3F2", "fontcolor": "#0A1A24", "style": "filled"},
    "standard":       {"shape": "folder",  "fillcolor": "#D8C7F2", "fontcolor": "#1A0F2E", "style": "filled"},
    "interpretation": {"shape": "box",     "fillcolor": "#F5F5F5", "fontcolor": "#1A1A1A", "style": "filled"},
    "threshold":      {"shape": "diamond", "fillcolor": "#FFF3B0", "fontcolor": "#3A2E00", "style": "filled"},
    "alternative":    {"shape": "box",     "fillcolor": "#E5E5E5", "fontcolor": "#1A1A1A", "style": "dashed,filled"},
    "conclusion":     {"shape": "box",     "fillcolor": "#A8E6E0", "fontcolor": "#0A2A28", "style": "filled", "penwidth": "2"},
    "open_question":  {"shape": "box",     "fillcolor": "#F2C5E8", "fontcolor": "#2A0F24", "style": "dashed,filled"},
}


_EDGE_LABELS_BY_KIND = {
    "interpretation": [("applies_to", "appliesTo"), ("anchors", "anchors")],
    "threshold":      [("inputs", "derivedFrom")],
    "conclusion":     [("supported_by", "supports")],
}


def _escape(text: str) -> str:
    """Escape a string for safe inclusion in a DOT label attribute."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _truncate(text: str, max_chars: int = 60) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _node_label(node) -> str:
    """Build a short multi-line DOT label for a node."""
    kind = node.kind
    nid = node.id
    if kind == "fact":
        body = _truncate(node.claim)
    elif kind == "standard":
        body = node.rule_id
    elif kind == "interpretation":
        body = _truncate(node.statement)
    elif kind == "threshold":
        body = f"{node.name} = {node.value}"
    elif kind == "alternative":
        body = _truncate(node.alternative)
    elif kind == "conclusion":
        zone = node.comfort_zone
        body = f"{_truncate(node.statement, 50)}\\n[conf {node.confidence:.2f}, {zone}]"
    elif kind == "open_question":
        prefix = "ESCALATE: " if getattr(node, "escalate_to_reviewer", False) else ""
        body = prefix + _truncate(node.question)
    else:
        body = nid
    return f"{nid}\\n{body}"


def to_dot(record: ReasoningRecord) -> str:
    """Render the full record as a Graphviz DOT digraph."""
    lines: list[str] = []
    lines.append(f'digraph "{_escape(record.case_id)}" {{')
    lines.append('  rankdir=LR;')
    lines.append('  node [fontname="Helvetica" fontsize="10"];')
    lines.append('  edge [fontname="Helvetica" fontsize="9" color="#555555"];')
    lines.append('  bgcolor="#FAFAFA";')

    # Nodes
    for nid, node in record.nodes.items():
        style = _STYLE_BY_KIND.get(node.kind, {})
        attrs = [f'label="{_escape(_node_label(node))}"']
        for key, val in style.items():
            attrs.append(f'{key}="{val}"')
        lines.append(f'  "{nid}" [{" ".join(attrs)}];')

    # Edges
    for nid, node in record.nodes.items():
        for field_name, edge_label in _EDGE_LABELS_BY_KIND.get(node.kind, []):
            for ref in getattr(node, field_name, []) or []:
                lines.append(f'  "{ref}" -> "{nid}" [label="{edge_label}"];')

    lines.append("}")
    return "\n".join(lines) + "\n"


def to_mermaid_headline(record: ReasoningRecord) -> str:
    """Render only Conclusions and their direct supporting nodes.

    Output is a Mermaid flowchart suitable for GitHub / Obsidian / docs viewers.
    Designed as a small inset for the memo header rather than a full record view.
    """
    lines: list[str] = ["flowchart LR"]

    conclusion_ids = [nid for nid, n in record.nodes.items() if n.kind == "conclusion"]
    if not conclusion_ids:
        # Empty or no-conclusion record: produce a syntactically valid empty flowchart
        return "\n".join(lines) + "\n"

    referenced: set[str] = set()
    for cid in conclusion_ids:
        for ref in record.nodes[cid].supported_by:
            referenced.add(ref)
    keep = set(conclusion_ids) | referenced

    # Mermaid node definitions
    for nid in keep:
        node = record.nodes.get(nid)
        if node is None:
            continue
        # Mermaid label: keep short
        if node.kind == "conclusion":
            label = f"{nid}: {_truncate(node.statement, 40)}"
            shape = ("[", "]")  # rectangle, conclusion gets a class
        elif node.kind == "fact":
            label = f"{nid}: {_truncate(node.claim, 40)}"
            shape = ("[", "]")
        elif node.kind == "standard":
            label = f"{nid}: {node.rule_id}"
            shape = ("[", "]")
        elif node.kind == "interpretation":
            label = f"{nid}: {_truncate(node.statement, 40)}"
            shape = ("[", "]")
        else:
            label = nid
            shape = ("[", "]")
        # Escape characters Mermaid struggles with inside [ ]: quotes, brackets.
        safe = label.replace('"', "'").replace("[", "(").replace("]", ")")
        lines.append(f'    {nid}{shape[0]}"{safe}"{shape[1]}')

    # Edges only for conclusions, since "keep" is exactly conclusions + their supports
    for cid in conclusion_ids:
        for ref in record.nodes[cid].supported_by:
            if ref in keep:
                lines.append(f"    {ref} --> {cid}")

    # Style conclusions
    lines.append("    classDef conclusion fill:#A8E6E0,stroke:#1EC4B4,stroke-width:2px;")
    if conclusion_ids:
        lines.append(f"    class {','.join(conclusion_ids)} conclusion;")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Interactive HTML viewer
# ---------------------------------------------------------------------------

# Cytoscape style mapping from node kind to fill/border/shape.
_CY_STYLE_BY_KIND = {
    "fact":           {"bg": "#BFE3F2", "border": "#5E9CB7", "shape": "round-rectangle"},
    "standard":       {"bg": "#D8C7F2", "border": "#7B5EA8", "shape": "round-tag"},
    "interpretation": {"bg": "#F5F5F5", "border": "#888888", "shape": "round-rectangle"},
    "threshold":      {"bg": "#FFF3B0", "border": "#B89A2E", "shape": "diamond"},
    "alternative":    {"bg": "#E5E5E5", "border": "#888888", "shape": "round-rectangle"},
    "conclusion":     {"bg": "#A8E6E0", "border": "#1EC4B4", "shape": "round-rectangle"},
    "open_question":  {"bg": "#F2C5E8", "border": "#B85EA8", "shape": "round-rectangle"},
}


def _build_cy_elements(record: ReasoningRecord) -> dict:
    """Build a Cytoscape elements payload (nodes + edges) from a record."""
    nodes = []
    for nid, node in record.nodes.items():
        if node.kind == "fact":
            short = _truncate(node.claim, 50)
        elif node.kind == "standard":
            short = node.rule_id
        elif node.kind == "interpretation":
            short = _truncate(node.statement, 50)
        elif node.kind == "threshold":
            short = f"{node.name} = {node.value}"
        elif node.kind == "alternative":
            short = _truncate(node.alternative, 50)
        elif node.kind == "conclusion":
            short = _truncate(node.statement, 50)
        elif node.kind == "open_question":
            short = _truncate(node.question, 50)
        else:
            short = nid
        confidence = getattr(node, "confidence", None)
        comfort_zone = getattr(node, "comfort_zone", None)
        nodes.append({
            "data": {
                "id": nid,
                "label": f"{nid}: {short}",
                "kind": node.kind,
                "confidence": confidence,
                "comfort_zone": comfort_zone,
            }
        })

    edges = []
    edge_id = 0
    for nid, node in record.nodes.items():
        for field_name, edge_label in _EDGE_LABELS_BY_KIND.get(node.kind, []):
            for ref in getattr(node, field_name, []) or []:
                edges.append({
                    "data": {
                        "id": f"e{edge_id}",
                        "source": ref,
                        "target": nid,
                        "label": edge_label,
                    }
                })
                edge_id += 1

    return {"nodes": nodes, "edges": edges}


def to_html(record: ReasoningRecord) -> str:
    """Render the record as a self-contained interactive HTML viewer.

    Uses Cytoscape.js + cytoscape-dagre from a CDN. The full record JSON is
    inlined so the viewer needs no server. Hierarchical layout, click-to-select
    side panel, three filters (kind, confidence, comfort zone).
    """
    elements = _build_cy_elements(record)
    record_json = json.loads(record.model_dump_json())

    style_blocks = []
    for kind, style in _CY_STYLE_BY_KIND.items():
        style_blocks.append({
            "selector": f'node[kind = "{kind}"]',
            "style": {
                "background-color": style["bg"],
                "border-color": style["border"],
                "border-width": 3 if kind == "conclusion" else 1,
                "shape": style["shape"],
            },
        })

    style_json = json.dumps(style_blocks)
    elements_json = json.dumps(elements)
    record_json_str = json.dumps(record_json)
    case_id = record.case_id

    html = _HTML_TEMPLATE
    html = html.replace("__CASE_ID__", _html_escape(case_id))
    html = html.replace("__ELEMENTS_JSON__", elements_json)
    html = html.replace("__STYLE_JSON__", style_json)
    html = html.replace("__RECORD_JSON__", record_json_str)
    return html


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Reasoning record: __CASE_ID__</title>
<style>
  html, body { margin: 0; padding: 0; height: 100%; font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; background: #FAFAFA; color: #1A1A1A; }
  .layout { display: flex; height: 100vh; }
  .left { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .right { width: 360px; border-left: 1px solid #DDDDDD; background: #FFFFFF; display: flex; flex-direction: column; }
  header { padding: 12px 16px; border-bottom: 1px solid #DDDDDD; background: #FFFFFF; }
  header h1 { font-size: 14px; margin: 0; font-weight: 600; }
  header .case-id { color: #666; font-size: 12px; margin-top: 2px; font-family: ui-monospace, "SF Mono", Menlo, monospace; }
  .filters { padding: 10px 16px; border-bottom: 1px solid #DDDDDD; background: #FFFFFF; display: flex; gap: 16px; align-items: center; flex-wrap: wrap; font-size: 12px; }
  .filters label { display: flex; align-items: center; gap: 4px; cursor: pointer; }
  .filters .group { display: flex; gap: 8px; align-items: center; }
  .filters .group-label { font-weight: 600; color: #555; margin-right: 4px; }
  .filters input[type="range"] { width: 100px; }
  #graph { flex: 1; min-height: 0; }
  .right h2 { font-size: 13px; margin: 0; padding: 12px 16px; border-bottom: 1px solid #DDDDDD; font-weight: 600; }
  .panel { padding: 14px 16px; overflow-y: auto; flex: 1; font-size: 13px; line-height: 1.5; }
  .panel.empty { color: #888; font-style: italic; }
  .panel .field { margin-bottom: 12px; }
  .panel .field .panel-label { font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
  .panel .field .value { color: #1A1A1A; word-wrap: break-word; }
  .panel .field code { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12px; background: #F0F0F0; padding: 1px 4px; border-radius: 3px; }
  .panel .kind-badge { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
  .panel .edges { margin-top: 4px; }
  .panel .edges .edge-row { font-size: 12px; color: #444; padding: 2px 0; }
  .panel .edges .edge-row a { color: #0066CC; text-decoration: none; cursor: pointer; }
  .panel .edges .edge-row a:hover { text-decoration: underline; }
  .panel pre { background: #F5F5F5; padding: 8px; border-radius: 4px; font-size: 11px; overflow-x: auto; max-height: 200px; }
  .legend { padding: 10px 16px; border-top: 1px solid #DDDDDD; font-size: 11px; }
  .legend .item { display: inline-flex; align-items: center; gap: 4px; margin-right: 12px; margin-bottom: 4px; }
  .legend .swatch { width: 10px; height: 10px; border-radius: 2px; border: 1px solid #888; }
</style>
</head>
<body>
<div class="layout">
  <div class="left">
    <header>
      <h1>Reasoning record</h1>
      <div class="case-id">__CASE_ID__</div>
    </header>
    <div class="filters">
      <div class="group">
        <span class="group-label">Kinds:</span>
        <label><input type="checkbox" class="kind-filter" value="fact" checked> Fact</label>
        <label><input type="checkbox" class="kind-filter" value="standard" checked> Standard</label>
        <label><input type="checkbox" class="kind-filter" value="interpretation" checked> Interp</label>
        <label><input type="checkbox" class="kind-filter" value="threshold" checked> Threshold</label>
        <label><input type="checkbox" class="kind-filter" value="alternative" checked> Alt</label>
        <label><input type="checkbox" class="kind-filter" value="conclusion" checked> Conclusion</label>
        <label><input type="checkbox" class="kind-filter" value="open_question" checked> Open Q</label>
      </div>
      <div class="group">
        <span class="group-label">Min confidence:</span>
        <input type="range" id="conf-filter" min="0" max="100" value="0" step="5">
        <span id="conf-value">0.00</span>
      </div>
      <div class="group">
        <span class="group-label">Comfort zone:</span>
        <select id="zone-filter">
          <option value="all" selected>All</option>
          <option value="in">In zone only</option>
          <option value="out">Out of zone only</option>
        </select>
      </div>
    </div>
    <div id="graph"></div>
    <div class="legend">
      <div class="item"><span class="swatch" style="background:#BFE3F2"></span>Fact</div>
      <div class="item"><span class="swatch" style="background:#D8C7F2"></span>Standard</div>
      <div class="item"><span class="swatch" style="background:#F5F5F5"></span>Interpretation</div>
      <div class="item"><span class="swatch" style="background:#FFF3B0"></span>Threshold</div>
      <div class="item"><span class="swatch" style="background:#E5E5E5"></span>Alternative</div>
      <div class="item"><span class="swatch" style="background:#A8E6E0; border-color:#1EC4B4"></span>Conclusion</div>
      <div class="item"><span class="swatch" style="background:#F2C5E8"></span>Open question</div>
    </div>
  </div>
  <div class="right">
    <h2>Selected node</h2>
    <div class="panel empty" id="panel">Click a node to see its details.</div>
  </div>
</div>

<script src="https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"
        integrity="sha384-IWROdLKRsN1UuJywMlWl7/blXQ8GEooN2n7dzTxfEPd7ybYIKCUJ2Ol/1Gpf3YV4"
        crossorigin="anonymous"></script>
<script src="https://unpkg.com/dagre@0.8.5/dist/dagre.min.js"
        integrity="sha384-2IH3T69EIKYC4c+RXZifZRvaH5SRUdacJW7j6HtE5rQbvLhKKdawxq6vpIzJ7j9M"
        crossorigin="anonymous"></script>
<script src="https://unpkg.com/cytoscape-dagre@2.5.0/cytoscape-dagre.js"
        integrity="sha384-u69h9ebXeSjlg6q/rb1zKTRAGu/h8deCl0409xpS/QJctMKnc4M9Fzkm01VOQdeF"
        crossorigin="anonymous"></script>
<script>
const ELEMENTS = __ELEMENTS_JSON__;
const KIND_STYLES = __STYLE_JSON__;
const RECORD = __RECORD_JSON__;

const KIND_COLORS = {
  fact: '#BFE3F2', standard: '#D8C7F2', interpretation: '#F5F5F5',
  threshold: '#FFF3B0', alternative: '#E5E5E5', conclusion: '#A8E6E0',
  open_question: '#F2C5E8',
};

const cy = cytoscape({
  container: document.getElementById('graph'),
  elements: { nodes: ELEMENTS.nodes, edges: ELEMENTS.edges },
  style: [
    {
      selector: 'node',
      style: {
        'label': 'data(label)',
        'text-wrap': 'wrap',
        'text-max-width': 180,
        'font-size': 10,
        'font-family': '-apple-system, "Segoe UI", Helvetica, Arial, sans-serif',
        'text-valign': 'center',
        'text-halign': 'center',
        'width': 'label',
        'height': 'label',
        'padding': '8px',
        'color': '#1A1A1A',
      },
    },
    ...KIND_STYLES,
    {
      selector: 'edge',
      style: {
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#888',
        'line-color': '#AAA',
        'width': 1.2,
        'label': 'data(label)',
        'font-size': 8,
        'color': '#777',
        'text-background-color': '#FAFAFA',
        'text-background-opacity': 0.85,
        'text-background-padding': 2,
      },
    },
    {
      selector: 'node:selected',
      style: {
        'border-color': '#FF6B35',
        'border-width': 4,
      },
    },
    {
      selector: '.hidden',
      style: { 'display': 'none' },
    },
  ],
  layout: {
    name: 'dagre',
    rankDir: 'LR',
    nodeSep: 25,
    rankSep: 80,
    edgeSep: 10,
  },
  wheelSensitivity: 0.2,
});

function applyFilters() {
  const checkedKinds = new Set(
    Array.from(document.querySelectorAll('.kind-filter:checked')).map(el => el.value)
  );
  const minConf = parseFloat(document.getElementById('conf-filter').value) / 100;
  document.getElementById('conf-value').textContent = minConf.toFixed(2);
  const zone = document.getElementById('zone-filter').value;

  cy.batch(() => {
    cy.nodes().forEach(node => {
      const data = node.data();
      let visible = checkedKinds.has(data.kind);

      if (visible && data.confidence !== null && data.confidence !== undefined) {
        if (data.confidence < minConf) visible = false;
      }

      if (visible && zone !== 'all' && data.comfort_zone) {
        if (data.comfort_zone !== zone) visible = false;
      }

      if (visible) node.removeClass('hidden');
      else node.addClass('hidden');
    });
    cy.edges().forEach(edge => {
      const src = cy.getElementById(edge.source().id());
      const tgt = cy.getElementById(edge.target().id());
      if (src.hasClass('hidden') || tgt.hasClass('hidden')) edge.addClass('hidden');
      else edge.removeClass('hidden');
    });
  });
}

document.querySelectorAll('.kind-filter').forEach(el => el.addEventListener('change', applyFilters));
document.getElementById('conf-filter').addEventListener('input', applyFilters);
document.getElementById('zone-filter').addEventListener('change', applyFilters);

function el(tag, opts) {
  const e = document.createElement(tag);
  if (opts) {
    if (opts.class) e.className = opts.class;
    if (opts.text !== undefined) e.textContent = opts.text;
    if (opts.style) e.setAttribute('style', opts.style);
    if (opts.dataNav !== undefined) e.setAttribute('data-nav', opts.dataNav);
    if (opts.tag === 'a') e.href = '#';
  }
  return e;
}

function field(labelText, valueNode) {
  const wrap = el('div', { class: 'field' });
  wrap.appendChild(el('div', { class: 'panel-label', text: labelText }));
  const valueWrap = el('div', { class: 'value' });
  if (typeof valueNode === 'string') {
    valueWrap.textContent = valueNode;
  } else {
    valueWrap.appendChild(valueNode);
  }
  wrap.appendChild(valueWrap);
  return wrap;
}

function codeNode(text) {
  const c = document.createElement('code');
  c.textContent = text;
  return c;
}

function navLink(targetId) {
  const a = document.createElement('a');
  a.href = '#';
  a.textContent = targetId;
  a.setAttribute('data-nav', targetId);
  return a;
}

function renderPanel(nodeId) {
  const panel = document.getElementById('panel');
  panel.classList.remove('empty');
  while (panel.firstChild) panel.removeChild(panel.firstChild);

  const node = RECORD.nodes[nodeId];
  if (!node) {
    panel.classList.add('empty');
    panel.textContent = 'Node not found.';
    return;
  }

  panel.appendChild(field('ID', codeNode(node.id)));

  const badge = document.createElement('span');
  badge.className = 'kind-badge';
  badge.style.background = KIND_COLORS[node.kind] || '#EEE';
  badge.textContent = node.kind;
  panel.appendChild(field('Kind', badge));

  if (node.kind === 'fact') {
    panel.appendChild(field('Claim', node.claim));
    panel.appendChild(field('Source', node.source));
  } else if (node.kind === 'standard') {
    const ruleWrap = document.createElement('span');
    ruleWrap.appendChild(codeNode(node.rule_id));
    ruleWrap.appendChild(document.createTextNode(' (v' + node.version + ')'));
    panel.appendChild(field('Rule', ruleWrap));
    panel.appendChild(field('Text', node.text));
  } else if (node.kind === 'interpretation') {
    panel.appendChild(field('Statement', node.statement));
  } else if (node.kind === 'threshold') {
    panel.appendChild(field('Name', node.name));
    panel.appendChild(field('Value', codeNode(String(node.value))));
    panel.appendChild(field('Derivation', node.derivation));
    if (node.sensitivity) panel.appendChild(field('Sensitivity', node.sensitivity));
  } else if (node.kind === 'alternative') {
    panel.appendChild(field('Alternative', node.alternative));
    panel.appendChild(field('Rejection reason', node.rejection_reason));
  } else if (node.kind === 'conclusion') {
    panel.appendChild(field('Statement', node.statement));
    let confText = node.confidence.toFixed(2) + ' — ' + node.comfort_zone + ' comfort zone';
    if (node.comfort_zone_reason) confText += ' (' + node.comfort_zone_reason + ')';
    panel.appendChild(field('Confidence', confText));
  } else if (node.kind === 'open_question') {
    panel.appendChild(field('Question', node.question));
    const escText = (node.escalate_to_reviewer ? 'Yes' : 'No') + ' (raised by ' + node.raised_by + ')';
    panel.appendChild(field('Escalate to reviewer', escText));
  }

  const cyNode = cy.getElementById(nodeId);
  const incoming = cyNode.incomers('edge');
  const outgoing = cyNode.outgoers('edge');

  if (incoming.length > 0) {
    const list = document.createElement('div');
    list.className = 'edges';
    incoming.forEach(e => {
      const row = document.createElement('div');
      row.className = 'edge-row';
      row.appendChild(navLink(e.source().id()));
      row.appendChild(document.createTextNode(' — ' + e.data('label') + ' →'));
      list.appendChild(row);
    });
    panel.appendChild(field('Incoming', list));
  }
  if (outgoing.length > 0) {
    const list = document.createElement('div');
    list.className = 'edges';
    outgoing.forEach(e => {
      const row = document.createElement('div');
      row.className = 'edge-row';
      row.appendChild(document.createTextNode('→ ' + e.data('label') + ' '));
      row.appendChild(navLink(e.target().id()));
      list.appendChild(row);
    });
    panel.appendChild(field('Outgoing', list));
  }

  const pre = document.createElement('pre');
  pre.textContent = JSON.stringify(node, null, 2);
  panel.appendChild(field('Raw JSON', pre));

  panel.querySelectorAll('a[data-nav]').forEach(a => {
    a.addEventListener('click', ev => {
      ev.preventDefault();
      const target = a.getAttribute('data-nav');
      cy.nodes().unselect();
      const tgt = cy.getElementById(target);
      if (tgt) {
        tgt.select();
        cy.animate({ center: { eles: tgt }, zoom: Math.max(cy.zoom(), 1.2) }, { duration: 250 });
        renderPanel(target);
      }
    });
  });
}

cy.on('tap', 'node', evt => renderPanel(evt.target.id()));
cy.on('tap', evt => {
  if (evt.target === cy) {
    cy.nodes().unselect();
    const panel = document.getElementById('panel');
    panel.classList.add('empty');
    while (panel.firstChild) panel.removeChild(panel.firstChild);
    panel.textContent = 'Click a node to see its details.';
  }
});
</script>
</body>
</html>
"""
