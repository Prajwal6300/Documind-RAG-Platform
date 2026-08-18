import sys

sys.stdout.reconfigure(encoding="utf-8")

from rag.rag_pipeline import answer_question, DEBUG_MODE

QUESTIONS = [
    "What is the leave policy?",
    "What are the working hours?",
    "What is the CEO's phone number?",
    "What is the supplier PO number PO-2026-0042?",
    "How many items are in the shipment?",
    "Summarize this document.",
]

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