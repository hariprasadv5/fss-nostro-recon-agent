"""Optional checker dashboard:  streamlit run app.py   (pip install streamlit)
Shows the latest run, lets a human checker approve or reject AI maker proposals."""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from recon_agent.audit import AuditLog          # noqa: E402
from recon_agent.config import SETTINGS          # noqa: E402

OUT = SETTINGS.output_dir
st.set_page_config(page_title="FSS Nostro Recon Agent", layout="wide")
st.title("FSS Nostro Reconciliation - Agentic AI (dummy data)")

if not (OUT / "run_summary.json").exists():
    if st.button("Run reconciliation"):
        from recon_agent.pipeline import run
        run(); st.rerun()
    st.stop()

s = json.loads((OUT / "run_summary.json").read_text())
c = st.columns(5)
c[0].metric("Auto-match rate", f"{s['auto_match_rate']:.1%}")
c[1].metric("Breaks", s["breaks"])
c[2].metric("Auto-resolved", s["by_decision"].get("AUTO_RESOLVE", 0))
c[3].metric("Awaiting checker", s["by_decision"].get("MAKER_PROPOSAL", 0))
c[4].metric("Escalated", s["by_decision"].get("ESCALATE", 0))
if st.button("Re-run reconciliation"):
    from recon_agent.pipeline import run
    run(); st.rerun()

acts = pd.read_csv(OUT / "actions_all.csv")
st.subheader("Breaks by category")
st.bar_chart(acts["category"].value_counts())

st.subheader("Escalations")
st.dataframe(acts[acts["decision"] == "ESCALATE"][["break_id", "account_id", "currency", "amount", "category",
                                                    "control_reason", "proposed_action"]], use_container_width=True)

st.subheader("Checker queue (four-eyes)")
q = pd.read_csv(OUT / "approval_queue.csv", dtype=str).fillna("")
inv = pd.read_csv(OUT / "breaks_investigated.csv", dtype=str).set_index("break_id")
checker = st.text_input("Your checker id (must differ from maker 'recon-agent')")
for i, r in q[q["status"] == "PENDING_CHECKER"].iterrows():
    with st.expander(f"{r['break_id']} | {r['currency']} {float(r['amount']):,.2f} | {r['category']} ({r['confidence']})"):
        st.write("**Root cause:**", inv.loc[r["break_id"], "root_cause"])
        st.write("**Proposed action:**", r["proposed_action"])
        st.write("**SOP citations:**", inv.loc[r["break_id"], "citations"])
        if r["draft_mt199"]:
            st.code(r["draft_mt199"])
        comment = st.text_input("Comment", key=f"c{i}")
        a, b = st.columns(2)
        for col, dec in ((a, "APPROVE"), (b, "REJECT")):
            if col.button(dec, key=f"{dec}{i}", disabled=not checker or checker == "recon-agent"):
                q.loc[i, ["checker", "checker_decision", "checker_comment", "status"]] = [
                    checker, dec, comment, "APPROVED" if dec == "APPROVE" else "REJECTED"]
                q.to_csv(OUT / "approval_queue.csv", index=False)
                AuditLog(OUT / "audit_log.jsonl", "DASHBOARD").log("HITL", f"CHECKER_{dec}", break_id=r["break_id"],
                                                                  checker=checker, comment=comment)
                st.rerun()
