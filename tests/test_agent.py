# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import pytest
from governed_reasoning.agent import ReasoningAgent
from governed_reasoning.bedrock_client import BedrockClient
from ._helpers import make_converse_response


def _valid_record_json(case_id: str = "c1") -> str:
    return json.dumps({
        "case_id": case_id,
        "nodes": {
            "f1": {"id": "f1", "kind": "fact", "claim": "Revenue $4.2M", "source": "WP-1"},
            "s1": {
                "id": "s1",
                "kind": "standard",
                "rule_id": "ASC 606-10-25-1",
                "version": "2026-05-15",
                "text": "An entity shall account...",
            },
            "a1": {
                "id": "a1",
                "kind": "alternative",
                "alternative": "Point-in-time recognition",
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
    })


def test_agent_produces_valid_record(mock_bedrock_session):
    mock_bedrock_session.converse.return_value = make_converse_response(_valid_record_json())
    agent = ReasoningAgent(BedrockClient())
    case = {
        "case_id": "c1",
        "case_body": "SaaS contract over 36 months at $100/month",
        "standards": "ASC 606-10-25-1: ...",
    }
    rec = agent.run(case)
    assert rec.case_id == "c1"
    assert "c1" in rec.nodes
    rec.validate_dag()


def test_agent_retries_once_on_invalid_json(mock_bedrock_session):
    mock_bedrock_session.converse.side_effect = [
        make_converse_response("not valid json"),
        make_converse_response(_valid_record_json()),
    ]
    agent = ReasoningAgent(BedrockClient())
    case = {"case_id": "c1", "case_body": "x", "standards": "y"}
    rec = agent.run(case)
    assert rec.case_id == "c1"
    assert mock_bedrock_session.converse.call_count == 2


def test_agent_raises_after_second_invalid_json(mock_bedrock_session):
    mock_bedrock_session.converse.side_effect = [
        make_converse_response("not valid"),
        make_converse_response("still not valid"),
    ]
    agent = ReasoningAgent(BedrockClient())
    with pytest.raises(ValueError, match="failed to produce valid record"):
        agent.run({"case_id": "c1", "case_body": "x", "standards": "y"})
