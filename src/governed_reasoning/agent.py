# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Reasoning agent: produces a typed reasoning record from a case."""

import json
from .bedrock_client import BedrockClient
from .prompts import AGENT_SYSTEM_PROMPT, AGENT_USER_TEMPLATE
from .schema import ReasoningRecord


REASONING_MODEL = "global.anthropic.claude-opus-4-7"


class ReasoningAgent:
    def __init__(self, client: BedrockClient, model_id: str = REASONING_MODEL):
        self.client = client
        self.model_id = model_id

    def run(self, case: dict) -> ReasoningRecord:
        user = AGENT_USER_TEMPLATE.format(
            case_id=case["case_id"],
            case_body=case["case_body"],
            standards=case["standards"],
        )
        last_error: Exception | None = None
        last_raw: str = ""
        for attempt in range(2):
            raw = self.client.invoke(
                model_id=self.model_id,
                system=AGENT_SYSTEM_PROMPT,
                user=user,
                max_tokens=16384,
            )
            last_raw = raw
            try:
                data = json.loads(raw)
                record = ReasoningRecord.model_validate(data)
                record.validate_dag()
                return record
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                if attempt == 1:
                    break
        preview = last_raw[:500] if last_raw else "<empty>"
        raise ValueError(
            f"agent failed to produce valid record after 2 attempts. "
            f"Last error: {last_error}. Last response (first 500 chars): {preview}"
        )
