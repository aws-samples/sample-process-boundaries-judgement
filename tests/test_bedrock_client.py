# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from governed_reasoning.bedrock_client import BedrockClient
from ._helpers import make_converse_response


def test_client_uses_east_profile_and_us_east_1(mock_bedrock_session, mocker):
    import boto3
    BedrockClient()
    boto3.Session.assert_called_with(profile_name="east", region_name="us-east-1")


def test_invoke_returns_text_from_converse(mock_bedrock_session):
    mock_bedrock_session.converse.return_value = make_converse_response("hello world")
    client = BedrockClient()
    out = client.invoke(
        model_id="global.anthropic.claude-opus-4-7",
        system="be helpful",
        user="hi",
    )
    assert out == "hello world"
    call_args = mock_bedrock_session.converse.call_args.kwargs
    assert call_args["modelId"] == "global.anthropic.claude-opus-4-7"
    assert call_args["system"] == [{"text": "be helpful"}]
    assert call_args["messages"][0]["content"][0]["text"] == "hi"


def test_invoke_passes_temperature_and_max_tokens(mock_bedrock_session):
    mock_bedrock_session.converse.return_value = make_converse_response("ok")
    client = BedrockClient()
    client.invoke(
        model_id="global.anthropic.claude-sonnet-4-6",
        system="s",
        user="u",
        temperature=0.0,
        max_tokens=2000,
    )
    cfg = mock_bedrock_session.converse.call_args.kwargs["inferenceConfig"]
    assert cfg["temperature"] == 0.0
    assert cfg["maxTokens"] == 2000


def test_invoke_omits_temperature_by_default(mock_bedrock_session):
    """Opus 4.7 (extended thinking) rejects temperature; default must omit it."""
    mock_bedrock_session.converse.return_value = make_converse_response("ok")
    client = BedrockClient()
    client.invoke(
        model_id="global.anthropic.claude-opus-4-7",
        system="s",
        user="u",
    )
    cfg = mock_bedrock_session.converse.call_args.kwargs["inferenceConfig"]
    assert "temperature" not in cfg
    assert cfg["maxTokens"] == 4096
