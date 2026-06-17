# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Adversarial validator: attacks a reasoning record and triggers agent extension."""

import json
from .bedrock_client import BedrockClient
from .prompts import (
    ADVERSARY_SYSTEM_PROMPT,
    ADVERSARY_USER_TEMPLATE,
    AGENT_RESPONSE_SYSTEM_PROMPT,
    AGENT_RESPONSE_USER_TEMPLATE,
)
from .schema import AdversarialChallenge, ReasoningRecord


ADVERSARY_MODEL = "global.anthropic.claude-sonnet-4-6"


class Adversary:
    def __init__(self, client: BedrockClient, model_id: str = ADVERSARY_MODEL):
        self.client = client
        self.model_id = model_id

    def attack(self, record: ReasoningRecord, case_body: str) -> list[AdversarialChallenge]:
        user = ADVERSARY_USER_TEMPLATE.format(
            case_id=record.case_id,
            case_body=case_body,
            record_json=record.model_dump_json(indent=2),
        )
        raw = self.client.invoke(
            model_id=self.model_id,
            system=ADVERSARY_SYSTEM_PROMPT,
            user=user,
            max_tokens=4096,
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"adversary returned invalid JSON: {e}") from e
        return [AdversarialChallenge.model_validate(c) for c in data]

    def run_validation_round(
        self,
        record: ReasoningRecord,
        case_body: str,
        agent,
        round_number: int = 1,
    ) -> ReasoningRecord:
        challenges = self.attack(record, case_body)
        if not challenges:
            return record

        challenges_json = json.dumps([c.model_dump() for c in challenges], indent=2)
        user = AGENT_RESPONSE_USER_TEMPLATE.format(
            record_json=record.model_dump_json(indent=2),
            challenges_json=challenges_json,
        )
        raw = agent.client.invoke(
            model_id=agent.model_id,
            system=AGENT_RESPONSE_SYSTEM_PROMPT,
            user=user,
            max_tokens=16384,
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"agent response returned invalid JSON: {e}") from e
        extended = ReasoningRecord.model_validate(data)
        extended.validate_dag()
        return extended
