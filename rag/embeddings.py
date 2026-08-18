import os

for _threading_var in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_threading_var, "1")
del _threading_var

from functools import lru_cache
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_model():
    return SentenceTransformer(MODEL_NAME)


def embed_documents(documents):
    if not documents:
        return []
    embeddings = get_model().encode(
        documents,
        normalize_embeddings=True
    )
    return embeddings.tolist()


def embed_query(query):
    if not query:
        return []
    embedding = get_model().encode(
        query,
        normalize_embeddings=True
    )
    return embedding.tolist()
