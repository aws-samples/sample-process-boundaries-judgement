# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from governed_reasoning.memo import MemoGenerator
from governed_reasoning.bedrock_client import BedrockClient
from governed_reasoning.schema import (
    ReasoningRecord, Fact, Conclusion, StandardReference, OpenQuestion,
)
from ._helpers import make_converse_response


def _record_with_open_question() -> ReasoningRecord:
    return ReasoningRecord(
        case_id="c1",
        nodes={
            "f1": Fact(id="f1", claim="Revenue $4.2M", source="WP-1"),
            "s1": StandardReference(
                id="s1", rule_id="ASC 606", version="2026-05-15", text="..."
            ),
            "q1": OpenQuestion(
                id="q1",
                question="Variable consideration treatment?",
                escalate_to_reviewer=True,
                raised_by="adversary",
            ),
            "c1": Conclusion(
                id="c1",
                statement="Recognize over time",
                confidence=0.85,
                comfort_zone="in",
                supported_by=["f1", "s1"],
            ),
        },
    )


def test_memo_generator_returns_markdown(mock_bedrock_session):
    mock_bedrock_session.converse.return_value = make_converse_response(
        "# Memo\n\n## Open Questions\n\n- [ref:q1] Variable consideration treatment?\n\n## Body\n\nRevenue [ref:f1] is recognized over time [ref:c1]."
    )
    gen = MemoGenerator(BedrockClient())
    memo = gen.render(_record_with_open_question())
    assert memo.startswith("# Memo")
    assert "[ref:q1]" in memo


def test_memo_uses_haiku_model(mock_bedrock_session):
    mock_bedrock_session.converse.return_value = make_converse_response("# Memo\n")
    gen = MemoGenerator(BedrockClient())
    gen.render(_record_with_open_question())
    call_args = mock_bedrock_session.converse.call_args.kwargs
    assert call_args["modelId"] == "global.anthropic.claude-haiku-4-5-20251001-v1:0"
