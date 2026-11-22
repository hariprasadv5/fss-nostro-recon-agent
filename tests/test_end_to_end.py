"""Acceptance test: run the full agentic pipeline on freshly generated dummy data."""
import runpy
import sys

import pandas as pd

from recon_agent.audit import verify_chain
from recon_agent.config import SETTINGS
from recon_agent.pipeline import run


def test_pipeline_meets_acceptance_criteria():
    sys.argv = ["gen", "--seed", "7", "--txns", "25"]
    runpy.run_path(str(SETTINGS.data_dir / "generate_dummy_data.py"), run_name="__main__")
    s = run()
    e = s["evaluation"]
    assert e["coverage"] == 1.0                       # every injected break is found
    assert e["accuracy"] >= 0.90                      # classification accuracy target
    assert e["suspicious_escalation_rate"] == 1.0     # no suspicious item slips through
    actions = pd.read_csv(SETTINGS.output_dir / "actions_all.csv")
    auto = actions[actions["decision"] == "AUTO_RESOLVE"]
    assert set(auto["category"]) <= set(SETTINGS.auto_action_categories)
    assert (auto["amount"] <= SETTINGS.auto_action_max_amount).all()
    assert verify_chain(SETTINGS.output_dir / "audit_log.jsonl")[0]
    # restore the default demo data set
    sys.argv = ["gen"]
    runpy.run_path(str(SETTINGS.data_dir / "generate_dummy_data.py"), run_name="__main__")
