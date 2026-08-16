from rag.vector_store import get_collection
from rag.embeddings import embed_query


def retrieve(query, top_k=5):

    collection = get_collection()

    query_embedding = embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    retrieved = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):

        retrieved.append({
            "text": document,
            "metadata": metadata,
            "distance": distance
        })

    return retrieved