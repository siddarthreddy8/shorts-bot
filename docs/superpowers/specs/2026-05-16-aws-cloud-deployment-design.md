# AWS Cloud Deployment — Design Spec

**Date:** 2026-05-16
**Status:** Approved
**Project:** Telugu → Hindi/English Shorts Bot

---

## Goal

Move the pipeline off the local Windows machine so it runs unattended every day. No manual intervention. The dashboard is accessible from a phone while the instance is running.

---

## Architecture

Two components only — one EC2 instance and an EBS volume. No always-on servers, no containers, no managed databases.

```
9:00am IST    EventBridge Scheduler fires (cron: 0 3:30 * * *)
              └─► Lambda (128MB) calls ec2.start_instances()

9:01am        EC2 t3.medium boots
              └─► systemd service runs pipeline automatically

              monitor → transcribe → script → render → upload
              (FastAPI + React dashboard served during this window)

~10:30am      Pipeline complete
              └─► final step calls ec2.stop_instances() on itself

              Dashboard goes offline until next day
```

---

## Infrastructure

| Component | Service | Detail |
|---|---|---|
| Pipeline compute | EC2 t3.medium | 2 vCPU, 4GB RAM — sufficient for Remotion + Chromium |
| Persistent storage | EBS 20GB gp3 | SQLite DB, code repo, `.env`, temp render files |
| Scheduler trigger | EventBridge Scheduler | Cron `0 3:30 * * *` (= 9:00am IST) |
| EC2 starter | AWS Lambda (Python 3.12) | EventBridge → `boto3.ec2.start_instances()` |
| Logs | CloudWatch Logs | Pipeline stdout/stderr streamed via CloudWatch agent |
| Region | us-east-1 | Lowest cost, widest service availability |

**Estimated cost: ~$4.50/month**
- EC2 t3.medium on-demand, ~2 hrs/day × 30 = ~$2.78
- EBS 20GB gp3 = ~$1.60
- Lambda + EventBridge = free tier (~$0)

---

## Pipeline Changes Required

### 1. Remove quality gate
The `QualityGate.tsx` component currently blocks auto-upload pending manual approval. On cloud this gate is removed — scripts auto-approve and flow directly to render → upload.

In the Python pipeline, the check for `_approved.txt` is replaced with an auto-approve step that writes the approved script file immediately after generation.

### 2. Self-shutdown
The last step of the pipeline calls:
```python
import boto3
boto3.client("ec2", region_name="us-east-1").stop_instances(
    InstanceIds=[_get_own_instance_id()]
)
```
`_get_own_instance_id()` reads from the EC2 instance metadata endpoint (`http://169.254.169.254/latest/meta-data/instance-id`).

### 3. Systemd service on boot
A systemd unit (`shorts-pipeline.service`) is configured to run on startup:
```ini
[Unit]
Description=Shorts Bot Pipeline
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=ec2-user
WorkingDirectory=/home/ec2-user/shorts-bot
ExecStart=/home/ec2-user/shorts-bot/.venv/bin/python -m src.main --run-pipeline
EnvironmentFile=/home/ubuntu/shorts-bot/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 4. Dashboard accessible during run
FastAPI + React are served on the EC2 public IP (port 8000) while the instance is running. No domain name required — access via `http://<ec2-public-ip>:8000`. The IP is stable per run (Elastic IP assigned).

---

## IAM Permissions

Two IAM roles are needed:

**Lambda execution role:**
- `ec2:StartInstances` on the pipeline EC2 instance ARN

**EC2 instance role:**
- `ec2:StopInstances` on itself (restricted by instance ID condition)
- `logs:CreateLogGroup`, `logs:PutLogEvents` for CloudWatch

---

## EC2 Setup (one-time)

1. Launch t3.medium, Amazon Linux 2023, attach EBS 20GB
2. Install: Python 3.12, Node.js 20, ffmpeg, Chromium (for Remotion)
3. Clone repo to `/home/ec2-user/shorts-bot`
4. Create `.venv`, `pip install -r requirements.txt`
5. `cd remotion && npm install`
6. Copy `.env` with all API keys (ElevenLabs, FAL, Claude, YouTube OAuth)
7. Configure systemd service
8. Assign Elastic IP
9. Attach EC2 instance role

---

## Error Handling

| Failure | Behaviour |
|---|---|
| Pipeline step fails | Logged to CloudWatch; instance still shuts down (prevent runaway cost) |
| EC2 fails to start | EventBridge retries twice; after that manual intervention needed |
| Render timeout (>30 min) | watchdog script kills pipeline, logs error, shuts down |
| YouTube upload error | Logged, video marked `upload_failed` in SQLite, retried next run |

---

## Out of Scope (this spec)

- Dashboard features and design (separate spec)
- Auto-scaling or multiple videos in parallel
- Moving SQLite to RDS
- HTTPS / custom domain for dashboard
- CI/CD pipeline for code deployments
