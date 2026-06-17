# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Shared pytest fixtures."""

from unittest.mock import MagicMock
import pytest


@pytest.fixture
def mock_bedrock_session(mocker):
    """Mock boto3.Session().client('bedrock-runtime') so no real calls happen."""
    fake_client = MagicMock()
    fake_session = MagicMock()
    fake_session.client.return_value = fake_client
    mocker.patch("boto3.Session", return_value=fake_session)
    return fake_client
