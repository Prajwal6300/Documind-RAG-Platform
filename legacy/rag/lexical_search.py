"""Lightweight, pure-Python BM25 and exact entity/phrase matching engine.

Provides zero-dependency lexical retrieval:
  - Okapi BM25 scoring with IDF (Inverse Document Frequency)
  - Exact entity / code / identifier matching (e.g., EMP-1042, PO-2026-0042, $4,500.00)
  - Multi-word exact phrase matching
  - Substring & keyword hit ratio
  - Fast in-memory execution (<2ms for hundreds of chunks)
"""

import math
import re
from collections import Counter


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[-_./][A-Za-z0-9]+)*|[\$₹€£]\d+(?:,\d+)*(?:\.\d+)?")
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "what", "which", "who",
    "whom", "whose", "when", "where", "how", "why", "do", "does", "did",
    "has", "have", "had", "of", "in", "on", "at", "for", "to", "from",
    "with", "by", "and", "or", "but", "not", "it", "its", "this", "that",
    "these", "those", "there", "their", "they", "he", "she", "his", "her",
    "him", "you", "your", "i", "me", "my", "we", "us", "our", "be", "been",
    "being", "about", "can", "could", "would", "should", "will", "shall",
    "may", "might", "please", "tell", "say", "give", "find", "show", "need",
    "want", "like", "any", "all", "some", "each", "every", "up", "down",
    "into", "over", "than", "also", "then", "so", "if", "as", "because",
    "via", "per", "etc", "within", "during", "without", "get", "know", "see",
}


def tokenize(text):
    """Tokenize text into lowercase words/numbers/identifiers."""
    if not text:
        return []
    text_lower = text.lower()
    tokens = _TOKEN_PATTERN.findall(text_lower)
    return tokens


def tokenize_meaningful(text):
    """Tokenize and filter out stopwords."""
    tokens = tokenize(text)
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def normalize_code_or_entity(val):
    """Normalize codes like 'EMP-1042' or 'EMP 1042' or 'emp1042' for matching."""
    if not val:
        return ""
    return re.sub(r"[\s\-_/]", "", str(val).lower())


class BM25Index:
    """In-memory BM25 index for candidate chunks."""

    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.doc_count = 0
        self.avg_doc_len = 0.0
        self.doc_lens = []
        self.doc_term_freqs = []
        self.doc_ids = []
        self.doc_chunks = []
        self.df = Counter()
        self.idf = {}

    def index_chunks(self, chunks):
        """Index a list of chunk dicts `[{'chunk_id', 'text', 'metadata'}, ...]`."""
        self.doc_chunks = chunks
        self.doc_count = len(chunks)
        self.doc_lens = []
        self.doc_term_freqs = []
        self.doc_ids = []
        self.df = Counter()
        self.idf = {}

        if self.doc_count == 0:
            self.avg_doc_len = 0.0
            return

        total_len = 0
        for chunk in chunks:
            text = chunk.get("text", "")
            tokens = tokenize_meaningful(text)
            doc_len = len(tokens)
            self.doc_lens.append(doc_len)
            total_len += doc_len
            self.doc_ids.append(chunk.get("chunk_id"))

            tf = Counter(tokens)
            self.doc_term_freqs.append(tf)

            for term in tf:
                self.df[term] += 1

        self.avg_doc_len = total_len / max(1, self.doc_count)

        # Precompute IDF for terms with standard BM25 formula
        for term, freq in self.df.items():
            idf_val = math.log(1.0 + (self.doc_count - freq + 0.5) / (freq + 0.5))
            self.idf[term] = max(0.1, idf_val)

    def score_query(self, query_tokens):
        """Compute BM25 scores for all indexed chunks for the given query tokens."""
        if not self.doc_count or not query_tokens:
            return []

        scores = []
        for idx, tf in enumerate(self.doc_term_freqs):
            doc_len = self.doc_lens[idx]
            score = 0.0
            len_norm = 1.0 - self.b + self.b * (doc_len / max(1.0, self.avg_doc_len))

            for token in query_tokens:
                if token in tf:
                    term_freq = tf[token]
                    idf = self.idf.get(token, 0.1)
                    numerator = term_freq * (self.k1 + 1.0)
                    denominator = term_freq + self.k1 * len_norm
                    score += idf * (numerator / denominator)

            scores.append((self.doc_chunks[idx], score))

        return scores


def calculate_exact_match_boost(query_text, entities, chunk_text):
    """Check for exact identifier, entity, or phrase matches in chunk text.

    Returns a boost score in [0.0, 1.0].
    """
    if not chunk_text:
        return 0.0

    chunk_lower = chunk_text.lower()
    chunk_norm = normalize_code_or_entity(chunk_text)
    boost = 0.0

    # 1. Exact entity matches (IDs, dates, amounts, codes, emails, phones)
    if entities:
        for _entity_type, val in entities:
            val_lower = str(val).lower().strip()
            val_norm = normalize_code_or_entity(val)

            if val_lower and val_lower in chunk_lower:
                boost = max(boost, 0.95)
            elif val_norm and len(val_norm) >= 3 and val_norm in chunk_norm:
                boost = max(boost, 0.90)

    # 2. Exact multi-word query phrase match
    cleaned_query = re.sub(r"[^\w\s]", " ", query_text.lower()).strip()
    words = cleaned_query.split()
    meaningful_words = [w for w in words if w not in _STOPWORDS and len(w) > 1]

    if len(meaningful_words) >= 2:
        phrase = " ".join(meaningful_words)
        if phrase in chunk_lower:
            boost = max(boost, 0.80)
        else:
            # Check bigram matches
            for i in range(len(meaningful_words) - 1):
                bigram = f"{meaningful_words[i]} {meaningful_words[i+1]}"
                if bigram in chunk_lower:
                    boost = max(boost, 0.50)
                    break

    return boost


def calculate_keyword_overlap(query_tokens, chunk_text):
    """Calculate the ratio of meaningful query tokens that appear in the chunk text."""
    meaningful = [t for t in query_tokens if t not in _STOPWORDS and len(t) > 1]
    if not meaningful or not chunk_text:
        return 0.0

    chunk_lower = chunk_text.lower()
    hits = sum(1 for token in meaningful if token.lower() in chunk_lower)
    return hits / len(meaningful)
