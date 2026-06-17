# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import pytest
from governed_reasoning.adversary import Adversary
from governed_reasoning.agent import ReasoningAgent
from governed_reasoning.bedrock_client import BedrockClient
from governed_reasoning.schema import ReasoningRecord, Fact, Conclusion, StandardReference, AlternativeConsidered
from ._helpers import make_converse_response


def _seed_record() -> ReasoningRecord:
    return ReasoningRecord(
        case_id="c1",
        nodes={
            "f1": Fact(id="f1", claim="Revenue $4.2M", source="WP-1"),
            "s1": StandardReference(
                id="s1", rule_id="ASC 606-10-25-1", version="2026-05-15", text="An entity shall..."
            ),
            "a1": AlternativeConsidered(
                id="a1",
                alternative="Point-in-time",
                rejection_reason="Performance obligation extends over term",
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


def test_adversary_returns_parsed_challenges(mock_bedrock_session):
    challenges = [
        {
            "dimension": "framing",
            "challenge": "Is ASC 606 even the right standard? This may be a license arrangement under 985-605.",
            "target_node_id": "s1",
        }
    ]
    mock_bedrock_session.converse.return_value = make_converse_response(json.dumps(challenges))
    adv = Adversary(BedrockClient())
    out = adv.attack(_seed_record(), case_body="SaaS contract...")
    assert len(out) == 1
    assert out[0].dimension == "framing"


def test_adversary_returns_empty_list_when_record_clean(mock_bedrock_session):
    mock_bedrock_session.converse.return_value = make_converse_response("[]")
    adv = Adversary(BedrockClient())
    out = adv.attack(_seed_record(), case_body="...")
    assert out == []


def test_validation_round_extends_record_via_agent_response(mock_bedrock_session):
    challenges = [
        {
            "dimension": "completeness",
            "challenge": "No mention of variable consideration constraint.",
            "target_node_id": None,
        }
    ]
    extended_record = {
        "case_id": "c1",
        "nodes": {
            **{
                "f1": {"id": "f1", "kind": "fact", "claim": "Revenue $4.2M", "source": "WP-1"},
                "s1": {
                    "id": "s1",
                    "kind": "standard",
                    "rule_id": "ASC 606-10-25-1",
                    "version": "2026-05-15",
                    "text": "An entity shall...",
                },
                "a1": {
                    "id": "a1",
                    "kind": "alternative",
                    "alternative": "Point-in-time",
                    "rejection_reason": "Performance obligation extends over term",
                },
                "c1": {
                    "id": "c1",
                    "kind": "conclusion",
                    "statement": "Recognize over time",
                    "confidence": 0.85,
                    "comfort_zone": "in",
                    "supported_by": ["f1", "s1"],
                },
            },
            "q1": {
                "id": "q1",
                "kind": "open_question",
                "question": "Variable consideration treatment under 606-10-32-11?",
                "escalate_to_reviewer": True,
                "raised_by": "adversary",
            },
        },
        "adversarial_rounds": [
            {
                "round_number": 1,
                "challenges": challenges,
                "agent_response_summary": "Added open_question for variable consideration; escalated to reviewer.",
            }
        ],
    }
    mock_bedrock_session.converse.side_effect = [
        make_converse_response(json.dumps(challenges)),
        make_converse_response(json.dumps(extended_record)),
    ]

    adv = Adversary(BedrockClient())
    agent = ReasoningAgent(BedrockClient())
    rec = adv.run_validation_round(_seed_record(), case_body="...", agent=agent)
    assert "q1" in rec.nodes
    assert len(rec.adversarial_rounds) == 1
    assert rec.adversarial_rounds[0].round_number == 1


def test_adversary_skips_response_when_no_challenges(mock_bedrock_session):
    mock_bedrock_session.converse.return_value = make_converse_response("[]")
    adv = Adversary(BedrockClient())
    agent = ReasoningAgent(BedrockClient())
    seed = _seed_record()
    rec = adv.run_validation_round(seed, case_body="...", agent=agent)
    assert rec.adversarial_rounds == []
    # Only one Bedrock call (adversary), no agent-response call
    assert mock_bedrock_session.converse.call_count == 1
