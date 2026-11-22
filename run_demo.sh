#!/usr/bin/env bash
set -e
export PYTHONPATH=src
python -m recon_agent.cli generate
python -m recon_agent.cli run
python -m recon_agent.cli verify-audit
echo "Open outputs/recon_report.md, then review outputs/approval_queue.csv"
