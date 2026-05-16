# AWS Cloud Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the shorts-bot pipeline to AWS so it runs fully automated daily — EventBridge starts an EC2 instance at 9am IST, the pipeline runs (monitor → transcribe → script → render → upload), then the instance stops itself.

**Architecture:** A single EC2 t3.medium instance with a persistent EBS volume runs the complete pipeline. EventBridge Scheduler triggers a Lambda function that starts the instance. A systemd service on the instance runs the pipeline on boot. The final pipeline step stops the instance via boto3. If Python crashes, a systemd safety net calls the AWS CLI to stop the instance regardless.

**Tech Stack:** Python (boto3, click), AWS (EC2, EBS, Lambda, EventBridge, IAM, CloudWatch), systemd, Amazon Linux 2023

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/pipeline/__init__.py` | Package marker |
| Create | `src/pipeline/auto_approve.py` | Write `_approved.txt` with Hindi + storytelling defaults |
| Create | `src/pipeline/shutdown.py` | Read EC2 instance ID from metadata; stop self via boto3 |
| Create | `src/pipeline/runner.py` | Orchestrate full automated pipeline end-to-end |
| Create | `tests/pipeline/__init__.py` | Package marker |
| Create | `tests/pipeline/test_auto_approve.py` | Tests for auto-approve |
| Create | `tests/pipeline/test_shutdown.py` | Tests for self-shutdown |
| Create | `tests/pipeline/test_runner.py` | Tests for pipeline runner |
| Create | `infra/__init__.py` | Package marker |
| Create | `infra/lambda_start_ec2.py` | Lambda handler: start EC2 instance |
| Create | `tests/infra/__init__.py` | Package marker |
| Create | `tests/infra/test_lambda_start_ec2.py` | Tests for Lambda handler |
| Create | `infra/shorts-pipeline.service` | systemd unit: run pipeline on boot, shutdown on exit |
| Create | `infra/setup_ec2.sh` | One-time EC2 provisioning script |
| Modify | `src/main.py` | Add `run-pipeline` CLI command |
| Modify | `requirements.txt` | Add `boto3>=1.35.0` |

---

## Task 1: Add boto3 dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add boto3 to requirements**

Open `requirements.txt`. After the `# Utils` section, add:

```
# AWS
boto3>=1.35.0
```

- [ ] **Step 2: Install it**

```bash
pip install boto3>=1.35.0
```

Expected: boto3 installs without errors.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add boto3 for AWS EC2 self-shutdown"
```

---

## Task 2: Auto-approve module

**Files:**
- Create: `src/pipeline/__init__.py`
- Create: `src/pipeline/auto_approve.py`
- Create: `tests/pipeline/__init__.py`
- Create: `tests/pipeline/test_auto_approve.py`

- [ ] **Step 1: Write failing tests**

Create `tests/pipeline/__init__.py` (empty).

Create `tests/pipeline/test_auto_approve.py`:

```python
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch


def _make_draft(scripts_dir: Path, video_id: str) -> None:
    draft = {
        "video_id": video_id,
        "language": "hindi",
        "styles": ["storytelling"],
        "hooks": ["एक गाँव में एक किसान था", "वह दिन था जब सब बदल गया"],
        "body": "यह कहानी है उस किसान की जो...",
        "cta": "ऐसी और कहानियों के लिए फॉलो करें।",
        "full_script": "...",
        "word_count": 50,
    }
    (scripts_dir / f"{video_id}_draft.json").write_text(
        json.dumps(draft), encoding="utf-8"
    )


def test_auto_approve_writes_approved_txt(tmp_path):
    _make_draft(tmp_path, "test123")
    with patch("src.pipeline.auto_approve._SCRIPTS_DIR", tmp_path):
        from src.pipeline.auto_approve import auto_approve
        approved_path = auto_approve("test123")
    assert approved_path.exists()
    content = approved_path.read_text(encoding="utf-8")
    assert "एक गाँव में एक किसान था" in content
    assert "यह कहानी है उस किसान की जो" in content
    assert "फॉलो करें" in content


def test_auto_approve_uses_first_hook(tmp_path):
    _make_draft(tmp_path, "test456")
    with patch("src.pipeline.auto_approve._SCRIPTS_DIR", tmp_path):
        from src.pipeline.auto_approve import auto_approve
        approved_path = auto_approve("test456")
    content = approved_path.read_text(encoding="utf-8")
    assert "एक गाँव में एक किसान था" in content
    assert "वह दिन था जब सब बदल गया" not in content


def test_auto_approve_raises_when_no_draft(tmp_path):
    with patch("src.pipeline.auto_approve._SCRIPTS_DIR", tmp_path):
        from src.pipeline.auto_approve import auto_approve
        with pytest.raises(FileNotFoundError, match="test789"):
            auto_approve("test789")
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/pipeline/test_auto_approve.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — module doesn't exist yet.

- [ ] **Step 3: Create package and implement auto_approve**

Create `src/pipeline/__init__.py` (empty).

Create `src/pipeline/auto_approve.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.utils.config import project_root
from src.utils.logger import logger

_SCRIPTS_DIR = project_root() / "data" / "scripts"


def auto_approve(video_id: str) -> Path:
    """Write an approved script for video_id using Hindi + storytelling defaults.

    Reads the draft JSON written by generate-script, picks the first hook,
    assembles hook + body + cta, and writes {video_id}_approved.txt.

    Returns the path to the approved script file.
    Raises FileNotFoundError if no draft exists.
    """
    import json

    draft_path = _SCRIPTS_DIR / f"{video_id}_draft.json"
    if not draft_path.exists():
        raise FileNotFoundError(
            f"No draft script at {draft_path}. "
            f"Run `generate-script {video_id}` first."
        )

    data = json.loads(draft_path.read_text(encoding="utf-8"))
    hook = data["hooks"][0] if data["hooks"] else ""
    body = data["body"]
    cta = data["cta"]
    full_script = f"{hook}\n\n{body}\n\n{cta}".strip()

    approved_path = _SCRIPTS_DIR / f"{video_id}_approved.txt"
    approved_path.write_text(full_script, encoding="utf-8")
    logger.info(f"Auto-approved [{video_id}] → {approved_path.name}")
    return approved_path
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/pipeline/test_auto_approve.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/__init__.py src/pipeline/auto_approve.py \
        tests/pipeline/__init__.py tests/pipeline/test_auto_approve.py
git commit -m "feat(pipeline): add auto-approve module (hindi + storytelling defaults)"
```

---

## Task 3: Self-shutdown module

**Files:**
- Create: `src/pipeline/shutdown.py`
- Create: `tests/pipeline/test_shutdown.py`

- [ ] **Step 1: Write failing tests**

Create `tests/pipeline/test_shutdown.py`:

```python
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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/pipeline/test_shutdown.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement shutdown module**

Create `src/pipeline/shutdown.py`:

```python
from __future__ import annotations

import urllib.request

import boto3

from src.utils.logger import logger

_METADATA_URL = "http://169.254.169.254/latest/meta-data/instance-id"


def _get_instance_id() -> str:
    """Read own EC2 instance ID from the instance metadata endpoint."""
    with urllib.request.urlopen(_METADATA_URL, timeout=2) as resp:
        return resp.read().decode()


def _is_on_ec2() -> bool:
    """Return True if running on an EC2 instance (metadata endpoint reachable)."""
    try:
        urllib.request.urlopen(_METADATA_URL, timeout=1)
        return True
    except OSError:
        return False


def stop_self(region: str = "us-east-1") -> None:
    """Stop the current EC2 instance.

    No-op with a warning if not running on EC2 (e.g. local dev).
    """
    if not _is_on_ec2():
        logger.warning("Not on EC2 — skipping self-shutdown (local run)")
        return

    instance_id = _get_instance_id()
    logger.info(f"Stopping EC2 instance {instance_id}...")
    client = boto3.client("ec2", region_name=region)
    client.stop_instances(InstanceIds=[instance_id])
    logger.info("Stop signal sent. Instance will shut down shortly.")
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/pipeline/test_shutdown.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/shutdown.py tests/pipeline/test_shutdown.py
git commit -m "feat(pipeline): add self-shutdown module with EC2 metadata detection"
```

---

## Task 4: Pipeline runner

**Files:**
- Create: `src/pipeline/runner.py`
- Create: `tests/pipeline/test_runner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/pipeline/test_runner.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

# Import runner at module level so patches applied inside tests correctly
# replace names in the already-imported module's namespace.
# (Importing inside a `with patch(...)` block would overwrite the patches
# when the module's top-level imports execute.)
from src.pipeline import runner


def _make_mock_video(video_id: str = "vid1") -> MagicMock:
    v = MagicMock()
    v.video_id = video_id
    v.url = f"https://youtube.com/watch?v={video_id}"
    v.title = f"Test Video {video_id}"
    return v


def test_run_processes_all_videos():
    videos = [_make_mock_video("vid1"), _make_mock_video("vid2")]

    with patch("src.pipeline.runner.init_db"), \
         patch("src.pipeline.runner.poll_channels", return_value=videos), \
         patch("src.pipeline.runner._process_video") as mock_process, \
         patch("src.pipeline.runner.stop_self"):
        runner.run()

    assert mock_process.call_count == 2
    mock_process.assert_any_call(videos[0])
    mock_process.assert_any_call(videos[1])


def test_run_shuts_down_when_no_videos():
    with patch("src.pipeline.runner.init_db"), \
         patch("src.pipeline.runner.poll_channels", return_value=[]), \
         patch("src.pipeline.runner.stop_self") as mock_shutdown:
        runner.run()

    mock_shutdown.assert_called_once()


def test_run_shuts_down_even_when_video_fails():
    videos = [_make_mock_video("vid_fail")]

    with patch("src.pipeline.runner.init_db"), \
         patch("src.pipeline.runner.poll_channels", return_value=videos), \
         patch("src.pipeline.runner._process_video", side_effect=RuntimeError("boom")), \
         patch("src.pipeline.runner.log_event"), \
         patch("src.pipeline.runner.stop_self") as mock_shutdown:
        runner.run()  # must not raise

    mock_shutdown.assert_called_once()


def test_run_continues_after_one_video_fails():
    vid1 = _make_mock_video("vid1")
    vid2 = _make_mock_video("vid2")
    results = []

    def fake_process(video):
        if video.video_id == "vid1":
            raise RuntimeError("vid1 exploded")
        results.append(video.video_id)

    with patch("src.pipeline.runner.init_db"), \
         patch("src.pipeline.runner.poll_channels", return_value=[vid1, vid2]), \
         patch("src.pipeline.runner._process_video", side_effect=fake_process), \
         patch("src.pipeline.runner.log_event"), \
         patch("src.pipeline.runner.stop_self"):
        runner.run()

    assert results == ["vid2"]
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/pipeline/test_runner.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement pipeline runner**

Create `src/pipeline/runner.py`:

```python
from __future__ import annotations

# Lightweight imports only at module level (safe for test collection).
# Heavy modules (torch/whisper, remotion subprocess, google oauth) are
# imported lazily inside _process_video so test imports don't pull in GPU libs.
from src.db.database import init_db, log_event
from src.monitor.youtube_monitor import poll_channels
from src.pipeline.auto_approve import auto_approve
from src.pipeline.shutdown import stop_self
from src.utils.logger import logger

_LANGUAGE = "hindi"
_STYLES = ["storytelling"]


def run() -> None:
    """Full automated pipeline: monitor → transcribe → script → approve → render → upload → shutdown.

    Always calls stop_self() at the end — even if no videos found or a video fails.
    Individual video failures are logged and skipped; the next video is still processed.
    """
    init_db()
    try:
        videos = poll_channels()
        if not videos:
            logger.info("No new videos found.")
            return

        logger.info(f"Processing {len(videos)} video(s)...")
        for video in videos:
            try:
                _process_video(video)
            except Exception as exc:
                logger.error(f"[{video.video_id}] pipeline failed: {exc}")
                log_event(video.video_id, "error", str(exc))
    finally:
        stop_self()


def _process_video(video) -> None:
    """Run all pipeline steps for a single video.

    Heavy imports are lazy here to avoid pulling torch/whisper into
    module-level imports (which would break test collection).
    """
    from src.script.rewriter import generate
    from src.transcribe.whisper_transcriber import run as transcribe
    from src.upload.uploader import upload
    from src.video.generator import render as video_render

    vid = video.video_id

    logger.info(f"[{vid}] step 1/5 — transcribing...")
    transcript = transcribe(vid, video.url)

    logger.info(f"[{vid}] step 2/5 — generating script ({_LANGUAGE}/{_STYLES[0]})...")
    generate(vid, transcript.text, language=_LANGUAGE, styles=_STYLES)

    logger.info(f"[{vid}] step 3/5 — auto-approving...")
    auto_approve(vid)

    logger.info(f"[{vid}] step 4/5 — rendering...")
    video_render(vid)

    logger.info(f"[{vid}] step 5/5 — uploading...")
    upload(vid)

    logger.info(f"[{vid}] ✓ done")
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/pipeline/test_runner.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/runner.py tests/pipeline/test_runner.py
git commit -m "feat(pipeline): add automated pipeline runner (Hindi/storytelling, always shuts down)"
```

---

## Task 5: Wire `run-pipeline` into CLI

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Add the `run-pipeline` command**

In `src/main.py`, add this block after the existing `cmd_run` function (after line 60):

```python
@cli.command("run-pipeline")
def cmd_run_pipeline() -> None:
    """Run full automated pipeline end-to-end, then stop the EC2 instance.

    Intended for cloud use: EventBridge starts the instance, this command
    runs on boot via systemd, and stops the instance when done.
    Locally it behaves the same but skips the shutdown step.
    """
    from src.pipeline.runner import run
    run()
```

- [ ] **Step 2: Smoke-test the CLI wiring**

```bash
python -m src.main --help
```

Expected output includes `run-pipeline` in the command list.

```bash
python -m src.main run-pipeline --help
```

Expected: shows the command help without errors.

- [ ] **Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: add run-pipeline CLI command for automated cloud execution"
```

---

## Task 6: Lambda start function

**Files:**
- Create: `infra/__init__.py`
- Create: `infra/lambda_start_ec2.py`
- Create: `tests/infra/__init__.py`
- Create: `tests/infra/test_lambda_start_ec2.py`

- [ ] **Step 1: Write failing tests**

Create `tests/infra/__init__.py` (empty).

Create `tests/infra/test_lambda_start_ec2.py`:

```python
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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/infra/test_lambda_start_ec2.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Create package and implement Lambda handler**

Create `infra/__init__.py` (empty).

Create `infra/lambda_start_ec2.py`:

```python
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

    print(f"[lambda_start_ec2] {instance_id} → {state}")
    return {"instanceId": instance_id, "state": state}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/infra/test_lambda_start_ec2.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Run full test suite — verify nothing broken**

```bash
pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add infra/__init__.py infra/lambda_start_ec2.py \
        tests/infra/__init__.py tests/infra/test_lambda_start_ec2.py
git commit -m "feat(infra): add Lambda function to start pipeline EC2 on schedule"
```

---

## Task 7: systemd service file

**Files:**
- Create: `infra/shorts-pipeline.service`

- [ ] **Step 1: Create the systemd unit**

Create `infra/shorts-pipeline.service`:

```ini
[Unit]
Description=Shorts Bot Automated Pipeline
# Wait for network before starting
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=ec2-user
WorkingDirectory=/home/ec2-user/shorts-bot

# Run pipeline with a 90-minute hard timeout
ExecStart=/usr/bin/timeout 5400 \
    /home/ec2-user/shorts-bot/.venv/bin/python -m src.main run-pipeline

# Safety net: stop EC2 even if Python crashes or times out
# (boto3 self-shutdown inside Python is the primary path;
#  this runs regardless of exit code)
ExecStopPost=/bin/bash -c \
    'aws ec2 stop-instances \
     --instance-ids "$(curl -sf http://169.254.169.254/latest/meta-data/instance-id)" \
     --region us-east-1 || true'

EnvironmentFile=/home/ec2-user/shorts-bot/.env
StandardOutput=journal
StandardError=journal
# Don't restart automatically — pipeline runs once per boot
Restart=no

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Commit**

```bash
git add infra/shorts-pipeline.service
git commit -m "feat(infra): add systemd service for pipeline auto-run on EC2 boot"
```

---

## Task 8: EC2 provisioning script

**Files:**
- Create: `infra/setup_ec2.sh`

- [ ] **Step 1: Create setup script**

Create `infra/setup_ec2.sh`:

```bash
#!/usr/bin/env bash
# One-time EC2 setup script for Amazon Linux 2023.
# Run as ec2-user after first SSH into the instance.
# Usage: bash setup_ec2.sh
set -euo pipefail

REPO_URL="https://github.com/YOUR_USERNAME/shorts-bot.git"  # replace with your repo URL
APP_DIR="/home/ec2-user/shorts-bot"

echo "=== [1/8] System packages ==="
sudo dnf update -y
sudo dnf install -y git ffmpeg chromium python3.12 python3.12-pip nodejs npm

echo "=== [2/8] AWS CLI (pre-installed on AL2023, verify) ==="
aws --version

echo "=== [3/8] Clone repository ==="
git clone "$REPO_URL" "$APP_DIR"
cd "$APP_DIR"

echo "=== [4/8] Python virtual environment ==="
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "=== [5/8] Remotion dependencies ==="
cd remotion && npm ci && cd ..

echo "=== [6/8] Copy .env (you must do this manually) ==="
echo "ACTION REQUIRED: scp your .env to $APP_DIR/.env"
echo "  scp .env ec2-user@<your-ec2-ip>:$APP_DIR/.env"
echo "Press ENTER once .env is in place..."
read -r

echo "=== [7/8] Initialize database ==="
.venv/bin/python -m src.main init

echo "=== [8/8] Install and enable systemd service ==="
sudo cp infra/shorts-pipeline.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable shorts-pipeline.service
echo "Service enabled. It will run on next boot."

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Assign an Elastic IP to this instance in AWS console"
echo "  2. Attach the EC2 IAM role (ec2-pipeline-role) in AWS console"
echo "  3. Create the Lambda function (see infra/lambda_start_ec2.py)"
echo "  4. Create EventBridge Scheduler rule (cron: 0 3:30 * * ? *)"
echo "  5. Test: sudo systemctl start shorts-pipeline.service"
echo "     Then: journalctl -fu shorts-pipeline.service"
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x infra/setup_ec2.sh
git add infra/setup_ec2.sh
git commit -m "feat(infra): add EC2 one-time setup script"
```

---

## Task 8b: FastAPI dashboard systemd service

The spec requires FastAPI + React to be accessible on the EC2 public IP while the instance is running. A second systemd service handles this independently of the pipeline.

**Files:**
- Create: `infra/shorts-dashboard.service`

- [ ] **Step 1: Build the React UI (add to setup script)**

In `infra/setup_ec2.sh`, after step 5 (remotion deps), add:

```bash
echo "=== [5b/8] Build React dashboard ==="
cd src/ui && npm ci && npm run build && cd ../..
```

- [ ] **Step 2: Create dashboard systemd service**

Create `infra/shorts-dashboard.service`:

```ini
[Unit]
Description=Shorts Bot Dashboard (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/shorts-bot
ExecStart=/home/ec2-user/shorts-bot/.venv/bin/uvicorn src.api.main:app \
    --host 0.0.0.0 --port 8000
EnvironmentFile=/home/ec2-user/shorts-bot/.env
Restart=on-failure
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Enable in setup script**

In `infra/setup_ec2.sh`, in Step 8 (systemd), add alongside the pipeline service:

```bash
sudo cp infra/shorts-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable shorts-pipeline.service shorts-dashboard.service
```

- [ ] **Step 4: Open port 8000 in EC2 security group**

AWS Console → EC2 → Security Groups → your instance's group → Inbound rules:
- Add rule: TCP port 8000, source = your phone's IP (or `0.0.0.0/0` if you accept public access)

- [ ] **Step 5: Commit**

```bash
git add infra/shorts-dashboard.service
git commit -m "feat(infra): add FastAPI dashboard systemd service for EC2"
```

---

## Task 9: AWS infrastructure setup (manual)

These steps are done in the AWS Console or CLI. No code changes.

- [ ] **Step 1: Create IAM role for EC2 (`ec2-pipeline-role`)**

In AWS Console → IAM → Roles → Create role:
- Trusted entity: EC2
- Add inline policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ec2:StopInstances",
      "Resource": "*",
      "Condition": {
        "StringEquals": {"ec2:ResourceTag/Name": "shorts-bot-pipeline"}
      }
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:us-east-1:*:log-group:/shorts-bot/*"
    }
  ]
}
```
- Role name: `ec2-pipeline-role`

- [ ] **Step 2: Launch EC2 instance**

AWS Console → EC2 → Launch Instance:
- Name: `shorts-bot-pipeline`
- AMI: Amazon Linux 2023 (64-bit x86)
- Instance type: `t3.medium`
- Key pair: create or use existing (save `.pem` securely)
- Storage: 20 GiB gp3 EBS (root volume)
- IAM instance profile: `ec2-pipeline-role`
- Security group: allow SSH (port 22) from your IP only

Save the Instance ID (e.g. `i-0abc123def456789`).

- [ ] **Step 3: Assign Elastic IP**

EC2 → Elastic IPs → Allocate → Associate with `shorts-bot-pipeline` instance.

Save the Elastic IP address.

- [ ] **Step 4: SSH in and run setup script**

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ec2-user@<elastic-ip>
# Once in:
bash setup_ec2.sh
```

Follow the prompts — scp your `.env` when asked.

- [ ] **Step 5: Create IAM role for Lambda (`lambda-start-ec2-role`)**

IAM → Roles → Create role:
- Trusted entity: Lambda
- Add inline policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ec2:StartInstances",
      "Resource": "arn:aws:ec2:us-east-1:YOUR_ACCOUNT_ID:instance/YOUR_INSTANCE_ID"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:us-east-1:*:*"
    }
  ]
}
```
Replace `YOUR_ACCOUNT_ID` and `YOUR_INSTANCE_ID`.
- Role name: `lambda-start-ec2-role`

- [ ] **Step 6: Create Lambda function**

Lambda → Create function:
- Name: `shorts-bot-start-pipeline`
- Runtime: Python 3.12
- Execution role: `lambda-start-ec2-role`

Paste the contents of `infra/lambda_start_ec2.py` into the inline editor.

Add environment variables:
- `PIPELINE_INSTANCE_ID` = `i-0abc123def456789` (your instance ID)
- `AWS_REGION` = `us-east-1`

Deploy the function. Run a test event (empty `{}`) — verify state returns `pending`.

- [ ] **Step 7: Create EventBridge Scheduler rule**

EventBridge → Scheduler → Create schedule:
- Name: `shorts-bot-daily`
- Schedule type: Recurring schedule → Cron
- Cron expression: `30 3 * * ? *` (= 9:00am IST = 3:30am UTC)
- Flexible time window: Off
- Target: Lambda function → `shorts-bot-start-pipeline`
- Retry policy: 2 retries

Enable the schedule.

---

## Task 10: First-run verification

- [ ] **Step 1: Manual test run via systemd**

SSH into the EC2 instance:

```bash
ssh -i your-key.pem ec2-user@<elastic-ip>
sudo systemctl start shorts-pipeline.service
```

Watch live logs in a second terminal:

```bash
journalctl -fu shorts-pipeline.service
```

Expected log sequence:
```
shorts-pipeline[PID]: Processing N video(s)...
shorts-pipeline[PID]: [vid_xxx] step 1/5 — transcribing...
shorts-pipeline[PID]: [vid_xxx] step 2/5 — generating script (hindi/storytelling)...
shorts-pipeline[PID]: [vid_xxx] step 3/5 — auto-approving...
shorts-pipeline[PID]: [vid_xxx] step 4/5 — rendering...
shorts-pipeline[PID]: [vid_xxx] step 5/5 — uploading...
shorts-pipeline[PID]: [vid_xxx] ✓ done
shorts-pipeline[PID]: Stopping EC2 instance i-0abc...
```

After the log ends, verify in AWS Console → EC2 that the instance state changes to `stopping` → `stopped`.

- [ ] **Step 2: Verify video on YouTube**

Check your YouTube Studio — the newly uploaded Short should appear within a few minutes.

- [ ] **Step 3: Wait for EventBridge trigger next day**

At 9:00am IST the following day, verify in AWS Console → EC2 that the instance starts automatically, runs, and stops.

- [ ] **Step 4: Check CloudWatch Logs**

CloudWatch → Log groups → search for `/aws/lambda/shorts-bot-start-pipeline` — verify the Lambda ran at 3:30am UTC.

Check the EC2 system log or journal for the pipeline output (enable CloudWatch agent for persistent logs if needed).
