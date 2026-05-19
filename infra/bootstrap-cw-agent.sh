Content-Type: text/cloud-boothook; charset="us-ascii"
MIME-Version: 1.0

#!/bin/bash
# Installs CloudWatch agent on first boot where it's missing.
# cloud-boothook runs every boot before systemd services start,
# but the `command -v` guard makes it a no-op once installed.
if ! command -v /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl &>/dev/null; then
    cd /home/ubuntu/shorts-bot
    git pull origin master
    curl -sO "https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb"
    dpkg -i -E amazon-cloudwatch-agent.deb
    rm -f amazon-cloudwatch-agent.deb
    cp /home/ubuntu/shorts-bot/infra/amazon-cloudwatch-agent.json \
        /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
    /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
        -a fetch-config -m ec2 \
        -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s
    systemctl enable amazon-cloudwatch-agent
fi
