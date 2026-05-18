#!/usr/bin/env bash
# One-time EC2 setup script for Ubuntu 24.04/26.04 LTS.
# Run as ubuntu after first SSH into the instance.
# Usage: bash setup_ec2.sh
set -euo pipefail

REPO_URL="https://github.com/siddarthreddy8/shorts-bot.git"
APP_DIR="/home/ubuntu/shorts-bot"

echo "=== [1/8] System packages ==="
sudo apt update -y
sudo apt upgrade -y
sudo apt install -y git ffmpeg python3.12 python3.12-venv python3-pip nodejs npm

echo "=== [1b/8] Add 4GB swap (required for Remotion rendering on low-RAM instance) ==="
if [ ! -f /swapfile ]; then
  sudo dd if=/dev/zero of=/swapfile bs=128M count=32
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
  echo "Swap enabled: $(free -h | grep Swap)"
else
  echo "Swap already exists, skipping."
fi

echo "=== [2/8] AWS CLI ==="
if ! command -v aws &> /dev/null; then
  curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
  sudo apt install -y unzip
  unzip awscliv2.zip
  sudo ./aws/install
  rm -rf aws awscliv2.zip
fi
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

echo "=== [5b/8] Build React dashboard ==="
cd src/ui && npm ci && npm run build && cd ../..

echo "=== [6/8] Copy .env (you must do this manually) ==="
echo "ACTION REQUIRED: open a new terminal and run:"
echo "  scp -i new_instance.pem D:/siddarth/youtube/shorts-bot/.env ubuntu@54.183.198.139:$APP_DIR/.env"
echo "Press ENTER once .env is in place..."
read -r

echo "=== [7/8] Initialize database ==="
.venv/bin/python -m src.main init

echo "=== [8/8] Install and enable systemd services ==="
sudo cp infra/shorts-pipeline.service /etc/systemd/system/
sudo cp infra/shorts-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable shorts-pipeline.service shorts-dashboard.service
echo "Services enabled. They will run on next boot."

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Attach the EC2 IAM role (ec2-pipeline-role) in AWS console"
echo "  2. Create the Lambda function (see infra/lambda_start_ec2.py)"
echo "  3. Create EventBridge Scheduler rule (cron: 0 3:30 * * ? *)"
echo "  4. Test: sudo systemctl start shorts-pipeline.service"
echo "     Then: journalctl -fu shorts-pipeline.service"
