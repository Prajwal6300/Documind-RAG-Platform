import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

sys.stdout.reconfigure(encoding="utf-8")

from backend.src.pipeline import answer_question, DEBUG_MODE

QUESTIONS = [
    "What is the leave policy?",
    "What are the working hours?",
    "What is the CEO''s phone number?",
    "What is the supplier PO number PO-2026-0042?",
    "How many items are in the shipment?",
    "Summarize this document.",
]


def run_pipeline_full():
    for q in QUESTIONS:
        print("=" * 70)
        result = answer_question(q, stream=False, debug=True)
        print(f"Q: {q}")
        print(f"A: {result['answer'][:300]}")
        print(f"  no_context={result['no_context']}")
        print(f"  sources={result.get('sources')}")
        dbg = result.get("debug") or {}
        print(f"  type={dbg.get('question_type')} sufficiency={dbg.get('sufficiency')}")
        print()


def test_pipeline_full():
    run_pipeline_full()


if __name__ == "__main__":
    run_pipeline_full()
