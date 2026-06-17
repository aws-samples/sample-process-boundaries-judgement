# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Thin wrapper over the Bedrock Converse API."""

import boto3
from botocore.config import Config


class BedrockClient:
    def __init__(self, profile_name: str = "east", region_name: str = "us-east-1"):
        self._session = boto3.Session(profile_name=profile_name, region_name=region_name)
        self._client = self._session.client(
            "bedrock-runtime",
            config=Config(read_timeout=600, connect_timeout=10, retries={"max_attempts": 2}),
        )

    def invoke(
        self,
        model_id: str,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> str:
        inference_config: dict = {"maxTokens": max_tokens}
        if temperature is not None:
            inference_config["temperature"] = temperature
        response = self._client.converse(
            modelId=model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig=inference_config,
        )
        return response["output"]["message"]["content"][0]["text"]
