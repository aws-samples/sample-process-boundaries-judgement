# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Test helpers (imported normally; not a conftest)."""


def make_converse_response(text: str) -> dict:
    """Build a fake Bedrock Converse API response."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": text}],
            }
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 20, "totalTokens": 30},
    }
