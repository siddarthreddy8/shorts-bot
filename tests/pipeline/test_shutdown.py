from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_get_instance_id_reads_metadata():
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.read.return_value = b"i-0abc123def456"

    with patch("urllib.request.urlopen", return_value=mock_response):
        from src.pipeline.shutdown import _get_instance_id
        assert _get_instance_id() == "i-0abc123def456"


def test_stop_self_calls_stop_instances():
    mock_ec2 = MagicMock()
    mock_ec2.stop_instances.return_value = {}

    with patch("src.pipeline.shutdown._get_instance_id", return_value="i-0abc123def456"), \
         patch("boto3.client", return_value=mock_ec2):
        from src.pipeline.shutdown import stop_self
        stop_self(region="us-east-1")

    mock_ec2.stop_instances.assert_called_once_with(InstanceIds=["i-0abc123def456"])


def test_is_on_ec2_returns_true_when_metadata_reachable():
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        from src.pipeline.shutdown import _is_on_ec2
        assert _is_on_ec2() is True


def test_is_on_ec2_returns_false_when_metadata_unreachable():
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=OSError("no route")):
        from src.pipeline.shutdown import _is_on_ec2
        assert _is_on_ec2() is False
