"""AWS Lambda function: start the pipeline EC2 instance.

Triggered by EventBridge Scheduler (cron: 0 3:30 * * * = 9:00am IST).

Required environment variables:
    PIPELINE_INSTANCE_ID  — EC2 instance ID to start (e.g. i-0abc123def456789)
    AWS_REGION            — AWS region (default: us-east-1)
"""
from __future__ import annotations

import os

import boto3


def handler(event: dict, context: object) -> dict:
    instance_id = os.environ["PIPELINE_INSTANCE_ID"]
    region = os.environ.get("AWS_REGION", "us-east-1")

    ec2 = boto3.client("ec2", region_name=region)
    response = ec2.start_instances(InstanceIds=[instance_id])
    state = response["StartingInstances"][0]["CurrentState"]["Name"]

    print(f"[lambda_start_ec2] {instance_id} -> {state}")
    return {"instanceId": instance_id, "state": state}
