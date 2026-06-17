# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Memo generator: renders a markdown narrative from a reasoning record."""

from .bedrock_client import BedrockClient
from .prompts import MEMO_SYSTEM_PROMPT, MEMO_USER_TEMPLATE
from .schema import ReasoningRecord


MEMO_MODEL = "global.anthropic.claude-haiku-4-5-20251001-v1:0"


class MemoGenerator:
    def __init__(self, client: BedrockClient, model_id: str = MEMO_MODEL):
        self.client = client
        self.model_id = model_id

    def render(self, record: ReasoningRecord) -> str:
        user = MEMO_USER_TEMPLATE.format(record_json=record.model_dump_json(indent=2))
        return self.client.invoke(
            model_id=self.model_id,
            system=MEMO_SYSTEM_PROMPT,
            user=user,
            max_tokens=4096,
        )
