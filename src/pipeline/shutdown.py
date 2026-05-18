from __future__ import annotations

import urllib.request

import boto3

from src.utils.logger import logger

_TOKEN_URL = "http://169.254.169.254/latest/api/token"
_METADATA_URL = "http://169.254.169.254/latest/meta-data/instance-id"


def _get_imdsv2_token() -> str | None:
    """Fetch an IMDSv2 session token. Returns None on failure (e.g. local dev)."""
    try:
        req = urllib.request.Request(
            _TOKEN_URL,
            method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.read().decode()
    except OSError:
        return None


def _get_instance_id() -> str:
    """Read own EC2 instance ID from the instance metadata endpoint."""
    token = _get_imdsv2_token()
    headers = {"X-aws-ec2-metadata-token": token} if token else {}
    req = urllib.request.Request(_METADATA_URL, headers=headers)
    with urllib.request.urlopen(req, timeout=2) as resp:
        return resp.read().decode()


def _is_on_ec2() -> bool:
    """Return True if running on an EC2 instance (metadata endpoint reachable)."""
    try:
        token = _get_imdsv2_token()
        headers = {"X-aws-ec2-metadata-token": token} if token else {}
        req = urllib.request.Request(_METADATA_URL, headers=headers)
        urllib.request.urlopen(req, timeout=1)
        return True
    except OSError:
        return False


def stop_self(region: str = "us-east-1") -> None:
    """Stop the current EC2 instance.

    No-op with a warning if not running on EC2 (e.g. local dev).
    """
    try:
        instance_id = _get_instance_id()
    except OSError:
        logger.warning("Not on EC2 — skipping self-shutdown (local run)")
        return

    logger.info(f"Stopping EC2 instance {instance_id}...")
    client = boto3.client("ec2", region_name=region)
    client.stop_instances(InstanceIds=[instance_id])
    logger.info("Stop signal sent. Instance will shut down shortly.")
