# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from governed_reasoning.schema import (
    AlternativeConsidered,
    Conclusion,
    Fact,
    Interpretation,
    OpenQuestion,
    ReasoningRecord,
    StandardReference,
    Threshold,
)
from governed_reasoning.visualize import to_dot, to_html, to_mermaid_headline


def _full_record() -> ReasoningRecord:
    return ReasoningRecord(
        case_id="case-x",
        nodes={
            "f1": Fact(id="f1", claim="Revenue $4.2M", source="WP-1"),
            "s1": StandardReference(
                id="s1",
                rule_id="ASC 606-10-25-1",
                version="2026-05-15",
                text="An entity shall account...",
            ),
            "i1": Interpretation(
                id="i1",
                statement="Performance obligation is satisfied over time",
                applies_to=["f1"],
                anchors=["s1"],
            ),
            "t1": Threshold(
                id="t1",
                name="materiality",
                value=250000,
                derivation="5% of pretax income",
                inputs=["f1"],
            ),
            "a1": AlternativeConsidered(
                id="a1",
                alternative="Point-in-time recognition",
                rejection_reason="Performance obligation extends over term",
            ),
            "c1": Conclusion(
                id="c1",
                statement="Recognize over time",
                confidence=0.85,
                comfort_zone="in",
                supported_by=["f1", "s1", "i1"],
            ),
            "q1": OpenQuestion(
                id="q1",
                question="Variable consideration?",
                escalate_to_reviewer=True,
            ),
        },
    )


def test_to_dot_includes_digraph_header():
    out = to_dot(_full_record())
    assert out.startswith("digraph ")
    assert "}" in out


def test_to_dot_renders_every_node():
    out = to_dot(_full_record())
    for nid in ["f1", "s1", "i1", "t1", "a1", "c1", "q1"]:
        assert f'"{nid}"' in out


def test_to_dot_color_codes_by_kind():
    out = to_dot(_full_record())
    # Each kind should produce at least one fillcolor declaration
    # We don't assert specific hex values — just that distinct kinds get distinct styling
    assert "fillcolor=" in out
    # Conclusion gets a bold border to stand out
    assert 'penwidth="2"' in out or "penwidth=2" in out


def test_to_dot_labels_edges_with_relationship():
    out = to_dot(_full_record())
    # supported_by -> "supports" or similar
    assert "supports" in out
    # interpretation edges
    assert "appliesTo" in out
    assert "anchors" in out
    # threshold edges
    assert "derivedFrom" in out


def test_mermaid_headline_includes_only_conclusions_and_supports():
    record = _full_record()
    out = to_mermaid_headline(record)
    # Must include the conclusion and its supports
    assert "c1" in out
    assert "f1" in out
    assert "s1" in out
    assert "i1" in out
    # Must NOT include nodes that don't feed any conclusion
    assert "t1" not in out  # threshold not in supported_by
    assert "a1" not in out  # alternative not in supported_by
    assert "q1" not in out  # open question


def test_mermaid_headline_has_flowchart_header():
    out = to_mermaid_headline(_full_record())
    assert out.startswith("flowchart")


def test_empty_record_produces_valid_output():
    rec = ReasoningRecord(case_id="empty", nodes={})
    dot = to_dot(rec)
    assert dot.startswith("digraph ")
    assert "}" in dot
    mmd = to_mermaid_headline(rec)
    assert mmd.startswith("flowchart")


def test_to_html_includes_doctype_and_cytoscape():
    out = to_html(_full_record())
    assert out.startswith("<!DOCTYPE html>")
    # Cytoscape and dagre must be loaded
    assert "cytoscape" in out
    assert "dagre" in out
    # The viewer container exists
    assert 'id="graph"' in out


def test_to_html_inlines_record_json():
    out = to_html(_full_record())
    # The record JSON is inlined as a JS const
    assert "const RECORD =" in out
    # Specific node ids from _full_record() should appear
    assert '"f1"' in out
    assert '"c1"' in out
    assert '"q1"' in out


def test_to_html_includes_three_filter_groups():
    out = to_html(_full_record())
    # Kind checkboxes
    assert 'class="kind-filter"' in out
    # Confidence slider
    assert 'id="conf-filter"' in out
    # Comfort zone selector
    assert 'id="zone-filter"' in out


def test_to_html_uses_kind_styling():
    out = to_html(_full_record())
    # The conclusion fill color (teal) and a fact color (blue) must be referenced
    # in the inlined Cytoscape style payload
    assert "#A8E6E0" in out  # conclusion fill
    assert "#BFE3F2" in out  # fact fill
    # Border-width 3 on conclusion (the bold-border emphasis)
    assert '"border-width": 3' in out or "'border-width': 3" in out


def test_to_html_cdn_scripts_have_integrity_hashes():
    """Subresource Integrity is required on CDN-loaded scripts."""
    out = to_html(_full_record())
    # Three CDN scripts (cytoscape, dagre, cytoscape-dagre) must each have an integrity hash
    assert out.count('integrity="sha384-') == 3
    # And crossorigin="anonymous" for SRI to work
    assert out.count('crossorigin="anonymous"') == 3


def test_to_dot_escapes_quotes_in_labels():
    rec = ReasoningRecord(
        case_id="case-x",
        nodes={
            "f1": Fact(id="f1", claim='He said "hello"', source="src"),
        },
    )
    out = to_dot(rec)
    # Either escaped quotes or replaced with something safe; what matters is
    # the output is parseable (no unescaped quotes inside label strings)
    label_lines = [line for line in out.splitlines() if 'label="' in line and "f1" in line]
    assert label_lines, "expected a label line for f1"
    for line in label_lines:
        # Count the quotes after `label=`; must be even (matched pairs)
        after_label = line.split("label=", 1)[1]
        # Strip the closing of the attribute list to isolate label content
        # A reasonable proxy: the line should not have an odd unescaped " inside the label
        # We just check the file is syntactically reasonable by counting backslash-escaped quotes
        # vs raw quotes in a way that won't false-positive
        assert '"hello"' not in after_label or '\\"hello\\"' in after_label
