from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)


def embed_documents(documents):
    embeddings = model.encode(
        documents,
        normalize_embeddings=True
    )

    return embeddings.tolist()


def embed_query(query):
    embedding = model.encode(
        query,
        normalize_embeddings=True
    )

    return embedding.tolist()