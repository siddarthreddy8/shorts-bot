from __future__ import annotations

from unittest.mock import MagicMock, patch


def _mock_urlopen_response(data: bytes) -> MagicMock:
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = data
    return resp


def test_get_instance_id_reads_metadata():
    with patch("urllib.request.urlopen", side_effect=[
        _mock_urlopen_response(b"fake-imdsv2-token"),
        _mock_urlopen_response(b"i-0abc123def456"),
    ]):
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


def test_stop_self_noops_when_not_on_ec2():
    with patch("src.pipeline.shutdown._get_instance_id", side_effect=OSError("no route")), \
         patch("boto3.client") as mock_boto3:
        from src.pipeline.shutdown import stop_self
        stop_self(region="us-east-1")

    mock_boto3.assert_not_called()
