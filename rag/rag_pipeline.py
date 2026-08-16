from rag.retriever import retrieve
from rag.llm import generate_answer


def answer_question(question):

    results = retrieve(
        query=question,
        top_k=5
    )

    if not results:
        return {
            "answer": "I could not find relevant information.",
            "sources": []
        }

    context_parts = []
    sources = []

    for result in results:

        metadata = result["metadata"]

        source = metadata.get("source", "Unknown")
        page = metadata.get("page")

        source_text = f"Source: {source}"

        if page:
            source_text += f", Page: {page}"

        context_parts.append(
            f"{source_text}\n"
            f"{result['text']}"
        )

        sources.append({
            "source": source,
            "page": page,
            "distance": result["distance"]
        })

    context = "\n\n---\n\n".join(context_parts)

    answer = generate_answer(
        question,
        context
    )

    return {
        "answer": answer,
        "sources": sources
    }