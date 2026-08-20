import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from backend.src.retrieval import (
    retrieve,
    retrieve_for_summary,
    classify_question,
    extract_keywords,
    extract_entities,
    expand_query,
    is_broad_question,
)

QUESTIONS = [
    "What is the leave policy?",
    "What are the working hours?",
    "What is the CEO''s phone number?",
    "Summarize this document.",
    "What is the supplier PO number PO-2026-0042?",
    "How many items are in the shipment?",
]


def run_pipeline_retrieval():
    for q in QUESTIONS:
        print("=" * 70)
        print(f"Q: {q}")
        print(f"  type={classify_question(q)} broad={is_broad_question(q)}")
        kw = extract_keywords(q)
        ent = extract_entities(q)
        exp = expand_query(q, keywords=kw, entities=ent)
        print(f"  keywords={kw}")
        print(f"  entities={ent}")
        print(f"  expansions={exp}")

        if is_broad_question(q) or classify_question(q) == "SUMMARY":
            results = retrieve_for_summary(summary_query=q)
        else:
            results = retrieve(
                query=q,
                top_k=8,
                expanded_queries=exp,
                query_keywords=kw,
            )

        if len(results) == 1 and "_no_relevant" in str(results[0]):
            print("  -> NO RELEVANT EVIDENCE")
            continue

        print(f"  -> {len(results)} chunk(s) passed:")
        for r in results:
            meta = r.get("metadata") or {}
            d_val = f"{r.get('distance'):.3f}" if r.get('distance') is not None else "None"
            kw_val = f"{r.get('keyword_ratio'):.2f}" if r.get('keyword_ratio') is not None else "0.00"
            print(
                f"     d={d_val} kw={kw_val} "
                f"{meta.get('source')} p={meta.get('page')} :: "
                f"{r.get('text', '')[:80].replace(chr(10), ' ')}"
            )


def test_pipeline_retrieval():
    run_pipeline_retrieval()


if __name__ == "__main__":
    run_pipeline_retrieval()
