import sys

sys.stdout.reconfigure(encoding="utf-8")

from rag.retriever import retrieve
from rag.question_analyzer import extract_keywords, extract_entities, expand_query
from rag.rag_pipeline import answer_question

QUESTIONS = [
    "What is the employee's name in the resume?",
    "What is the joining date?",
    "What is the leave policy?",
    "What are the working hours?",
    "What is the CEO's favorite color?",
]

for q in QUESTIONS:
    print("=" * 70)
    kw = extract_keywords(q)
    ent = extract_entities(q)
    exp = expand_query(q, keywords=kw, entities=ent)
    results = retrieve(query=q, top_k=8, expanded_queries=exp, query_keywords=kw)

    if len(results) == 1 and "_no_relevant" in str(results[0]):
        print(f"Q: {q}\n  -> NO RELEVANT")
    else:
        print(f"Q: {q}")
        for r in results:
            meta = r.get("metadata") or {}
            dist = r.get("distance")
            dstr = f"{dist:.3f}" if dist is not None else "kw  "
            print(
                f"  d={dstr} kw={r.get('keyword_ratio'):.2f} "
                f"src={r.get('source_match'):.1f} score={r.get('_score'):.3f} "
                f"{meta.get('source')} p={meta.get('page')}"
            )
            print(f"    {r.get('text', '')[:80]}")

    print()
    r = answer_question(q, stream=False)
    print(f"  ANSWER: {r['answer'][:200]}")
    print(f"  no_context={r['no_context']}")
    print()