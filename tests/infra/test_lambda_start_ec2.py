from __future__ import annotations

import os
from unittest.mock import MagicMock, patch


def test_handler_starts_correct_instance():
    mock_ec2 = MagicMock()
    mock_ec2.start_instances.return_value = {
        "StartingInstances": [{"CurrentState": {"Name": "pending"}}]
    }

    env = {"PIPELINE_INSTANCE_ID": "i-0test123abc", "AWS_REGION": "us-east-1"}
    with patch.dict(os.environ, env), patch("boto3.client", return_value=mock_ec2):
        from infra import lambda_start_ec2
        result = lambda_start_ec2.handler({}, {})

    mock_ec2.start_instances.assert_called_once_with(InstanceIds=["i-0test123abc"])
    assert result == {"instanceId": "i-0test123abc", "state": "pending"}


def test_handler_returns_instance_state():
    mock_ec2 = MagicMock()
    mock_ec2.start_instances.return_value = {
        "StartingInstances": [{"CurrentState": {"Name": "running"}}]
    }

    env = {"PIPELINE_INSTANCE_ID": "i-0test999", "AWS_REGION": "eu-west-1"}
    with patch.dict(os.environ, env), patch("boto3.client", return_value=mock_ec2):
        from infra import lambda_start_ec2
        result = lambda_start_ec2.handler({}, {})

    assert result["state"] == "running"
    assert result["instanceId"] == "i-0test999"


def test_handler_raises_when_instance_id_missing():
    import pytest
    env_without_id = {k: v for k, v in os.environ.items() if k != "PIPELINE_INSTANCE_ID"}
    with patch.dict(os.environ, env_without_id, clear=True), \
         patch("boto3.client"):
        from infra import lambda_start_ec2
        with pytest.raises(KeyError):
            lambda_start_ec2.handler({}, {})
