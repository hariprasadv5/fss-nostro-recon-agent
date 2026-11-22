"""Central configuration. Values can be overridden with environment variables (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    # --- paths -----------------------------------------------------------
    data_dir: Path = ROOT / "data"
    statements_dir: Path = ROOT / "data" / "statements"
    ledger_file: Path = ROOT / "data" / "ledger_entries.csv"
    ground_truth_file: Path = ROOT / "data" / "ground_truth.csv"
    accounts_file: Path = ROOT / "data" / "nostro_accounts.csv"
    kb_dir: Path = ROOT / "knowledge_base"
    output_dir: Path = ROOT / "outputs"

    # --- LLM -------------------------------------------------------------
    llm_provider: str = os.getenv("LLM_PROVIDER", "auto")          # auto | openai | mock
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0"))
    prompt_version: str = "investigator-v1.2"

    # --- RAG -------------------------------------------------------------
    retriever: str = os.getenv("RETRIEVER", "auto")                # auto | chroma | tfidf
    top_k: int = int(os.getenv("RAG_TOP_K", "3"))

    # --- matching rules ----------------------------------------------------
    amount_tolerance: float = float(os.getenv("AMOUNT_TOLERANCE", "1.00"))     # rounding / FX tolerance
    fuzzy_ref_threshold: float = float(os.getenv("FUZZY_REF_THRESHOLD", "0.60"))
    date_window_days: int = int(os.getenv("DATE_WINDOW_DAYS", "2"))

    # --- guardrails / control limits -----------------------------------------
    auto_action_max_amount: float = float(os.getenv("AUTO_ACTION_MAX_AMOUNT", "250"))   # per item, account ccy
    auto_action_min_confidence: float = float(os.getenv("AUTO_ACTION_MIN_CONFIDENCE", "0.90"))
    escalation_amount: float = float(os.getenv("ESCALATION_AMOUNT", "1000000"))
    auto_action_categories: tuple = ("ROUNDING_FX_DIFFERENCE",)
    allowed_categories: tuple = field(default_factory=lambda: (
        "TIMING_DIFFERENCE", "BANK_CHARGES", "INTEREST", "DUPLICATE_POSTING",
        "ROUNDING_FX_DIFFERENCE", "AMOUNT_MISMATCH", "MISSING_IN_LEDGER",
        "MISSING_IN_STATEMENT", "UNIDENTIFIED_RECEIPT", "SUSPICIOUS",
    ))


SETTINGS = Settings()
