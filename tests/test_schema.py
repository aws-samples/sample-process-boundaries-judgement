# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import pytest
from pydantic import ValidationError
from governed_reasoning.schema import (
    Fact,
    StandardReference,
    Interpretation,
    Threshold,
    AlternativeConsidered,
    Conclusion,
    OpenQuestion,
    ReasoningRecord,
)


def test_fact_requires_id_claim_and_source():
    f = Fact(id="f1", claim="Revenue was $4.2M", source="Workpaper R-12")
    assert f.id == "f1"
    assert f.claim == "Revenue was $4.2M"


def test_standard_reference_captures_text_at_time_of_use():
    s = StandardReference(
        id="s1",
        rule_id="ASC 606-10-25-1",
        version="2026-05-15",
        text="An entity shall account for a contract...",
    )
    assert s.version == "2026-05-15"
    assert "contract" in s.text


def test_conclusion_requires_supporting_nodes():
    with pytest.raises(ValidationError):
        Conclusion(
            id="c1",
            statement="Revenue is recognized over time",
            confidence=0.9,
            comfort_zone="in",
            supported_by=[],
        )


def test_threshold_must_have_derivation():
    with pytest.raises(ValidationError):
        Threshold(
            id="t1",
            name="materiality",
            value=250000,
            derivation="",
            inputs=[],
        )


def test_record_validates_no_cycles():
    rec = ReasoningRecord(
        case_id="case-1",
        nodes={
            "f1": Fact(id="f1", claim="x", source="src"),
            "s1": StandardReference(id="s1", rule_id="r", version="v", text="t"),
            "c1": Conclusion(
                id="c1",
                statement="result",
                confidence=0.8,
                comfort_zone="in",
                supported_by=["f1", "s1"],
            ),
        },
    )
    rec.validate_dag()  # should not raise


def test_record_rejects_dangling_references():
    with pytest.raises(ValueError, match="references unknown node"):
        rec = ReasoningRecord(
            case_id="case-1",
            nodes={
                "c1": Conclusion(
                    id="c1",
                    statement="result",
                    confidence=0.8,
                    comfort_zone="in",
                    supported_by=["does-not-exist"],
                ),
            },
        )
        rec.validate_dag()


def test_open_question_node_first_class():
    q = OpenQuestion(
        id="q1",
        question="Should accelerated revenue clause be a separate POB?",
        escalate_to_reviewer=True,
    )
    assert q.escalate_to_reviewer is True


def test_alternative_considered_explains_rejection():
    a = AlternativeConsidered(
        id="a1",
        alternative="Treat as point-in-time",
        rejection_reason="Performance obligation extends over contract term",
    )
    assert "performance" in a.rejection_reason.lower()
