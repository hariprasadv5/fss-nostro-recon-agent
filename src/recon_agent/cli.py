"""Command line entry point.

  python -m recon_agent.cli generate           # (re)create dummy data
  python -m recon_agent.cli run                # run the agentic reconciliation
  python -m recon_agent.cli approve [--interactive --checker ID]
  python -m recon_agent.cli verify-audit       # check the audit hash chain
  python -m recon_agent.cli ask "question"     # ask the SOP knowledge base (RAG)
"""
from __future__ import annotations

import argparse
import json
import runpy
import sys

from .config import SETTINGS


def main(argv=None):
    ap = argparse.ArgumentParser(prog="recon_agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate"); g.add_argument("--seed", type=int, default=42); g.add_argument("--txns", type=int, default=40)
    sub.add_parser("run")
    a = sub.add_parser("approve"); a.add_argument("--interactive", action="store_true"); a.add_argument("--checker")
    sub.add_parser("verify-audit")
    q = sub.add_parser("ask"); q.add_argument("question")
    args = ap.parse_args(argv)

    if args.cmd == "generate":
        sys.argv = ["generate_dummy_data.py", "--seed", str(args.seed), "--txns", str(args.txns)]
        runpy.run_path(str(SETTINGS.data_dir / "generate_dummy_data.py"), run_name="__main__")
    elif args.cmd == "run":
        from .pipeline import run
        s = run()
        print(json.dumps({k: s[k] for k in ("run_id", "llm", "retriever", "matching", "auto_match_rate",
                                            "breaks", "by_decision")}, indent=2))
        if "evaluation" in s:
            e = s["evaluation"]
            print(f"Evaluation: accuracy {e['accuracy']:.1%}, coverage {e['coverage']:.1%}, "
                  f"suspicious escalated {e['suspicious_escalation_rate']:.1%}")
        print(f"Outputs written to {SETTINGS.output_dir}")
    elif args.cmd == "approve":
        from .hitl import apply_decisions
        print(apply_decisions(args.interactive, args.checker))
    elif args.cmd == "verify-audit":
        from .audit import verify_chain
        ok, n = verify_chain(SETTINGS.output_dir / "audit_log.jsonl")
        print(f"Audit chain {'INTACT' if ok else 'BROKEN at record ' + str(n)} ({n} records checked)")
        sys.exit(0 if ok else 1)
    elif args.cmd == "ask":
        from .rag import KnowledgeBase
        kb = KnowledgeBase(SETTINGS.kb_dir, SETTINGS.retriever, SETTINGS.output_dir / "chroma")
        for h in kb.search(args.question, SETTINGS.top_k):
            print(f"\n[{h['source']} > {h['section']}] score={h['score']}\n{h['text']}")


if __name__ == "__main__":
    main()
