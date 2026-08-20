"""Lightweight, dependency-free question analysis and normalization for the RAG pipeline.

Performs:
  - Question normalization (casing, punctuation, question boilerplate, singular/plural)
  - Question intent classification (identity, skills, education, experience, dates, compensation, policies, identifiers, etc.)
  - Question type classification (FACT, LIST, EXPLANATION, COMPARISON, SUMMARY, MULTI_PART)
  - Keyword & phrase extraction
  - Entity extraction (IDs, codes, dates, amounts, percentages, emails, phones, URLs)
  - Local query expansion & synonyms with multi-part decomposition (zero LLM calls)
  - Follow-up question resolution from conversation history
"""

import re

# ---------------------------------------------------------------------------
# Query Normalization & Boilerplate Stripping
# ---------------------------------------------------------------------------

_BOILERPLATE_PATTERNS = [
    r"^(?:please\s+)?(?:tell\s+me|show\s+me|give\s+me|find|what\s+is|what\s+are|what\s+was|what\s+were|who\s+is|who\s+was|where\s+is|where\s+did|when\s+is|when\s+did|how\s+much\s+is|how\s+many|can\s+you\s+tell\s+me|could\s+you\s+tell\s+me|i\s+want\s+to\s+know)\s+",
    r"\b(?:in\s+the\s+document|in\s+the\s+uploaded\s+document|in\s+the\s+uploaded\s+file|in\s+this\s+document|in\s+this\s+file|from\s+the\s+document|from\s+the\s+resume|from\s+the\s+pdf|from\s+the\s+file)\b",
    r"\b(?:according\s+to\s+the\s+document|as\s+per\s+the\s+document)\b",
]

_SINGULAR_PLURAL_MAP = {
    "skills": "skill",
    "policies": "policy",
    "requirements": "requirement",
    "employees": "employee",
    "dates": "date",
    "salaries": "salary",
    "leaves": "leave",
    "hours": "hour",
    "projects": "project",
    "technologies": "technology",
    "products": "product",
    "prices": "price",
    "items": "item",
    "details": "detail",
    "guidelines": "guideline",
    "rules": "rule",
    "benefits": "benefit",
}


def normalize_query_text(question: str) -> str:
    """Normalize query for search: lowercase, punctuation cleaning, whitespace collapse."""
    if not question:
        return ""
    q = question.lower()
    q = re.sub(r"[^\w\s\-$₹€£%./:@]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def strip_question_boilerplate(question: str) -> str:
    """Extract the semantic core of a question by removing conversational filler."""
    q = normalize_query_text(question)
    for pat in _BOILERPLATE_PATTERNS:
        q = re.sub(pat, " ", q, flags=re.IGNORECASE).strip()
    q = re.sub(r"\s+", " ", q).strip()
    return q


# ---------------------------------------------------------------------------
# Question Type Classification
# ---------------------------------------------------------------------------

_SUMMARY_HINTS = (
    "summar",
    "overview",
    "key point",
    "key takeaway",
    "important information",
    "main idea",
    "high level",
    "main point",
    "what is this document",
    "what are the main",
    "briefly describe",
    "in short",
    "give me the gist",
    "what does the document",
    "all the important",
    "key things",
    "tell me everything",
    "complete profile",
)

_LIST_HINTS = (
    "list all",
    "list the",
    "what are all",
    "all the skills",
    "all the policies",
    "all the requirements",
    "all the features",
    "all of the",
    "name all",
    "enumerate",
    "every skill",
    "every requirement",
    "what skills",
    "what technologies",
    "which of the following",
    "which of these",
    "give me a list",
    "what are the different",
    "what items",
    "what options",
    "all products",
    "all items",
)

_COMPARISON_HINTS = (
    "difference between",
    "compare",
    "versus",
    " vs ",
    "vs.",
    "similarities",
    "how does a compare to",
    "differ from",
    "difference from",
    "both x and y",
    "which is better",
)

_EXPLANATION_HINTS = (
    "explain",
    "why",
    "how does",
    "how do",
    "how is",
    "how are",
    "describe",
    "what is the process",
    "what does that mean",
    "in detail",
    "elaborate",
    "how does it work",
    "reason for",
)

_MULTI_PART_PATTERN = re.compile(
    r"\?\s+(?:and|also|then)\s+.+\?"
    r"|\bwhat (?:is|are|was|were) .+ and what "
    r"|\b(?:is|are|was|were) .+ and (?:what|who|when|where|how|why) "
    r"|\b(?:also|additionally|moreover|then)\b.*\?"
    r"|\b(?:tell me|find|get)\s+.+\s+and\s+.+"
)


def classify_question(question: str) -> str:
    """Classify a question into a lightweight type (no LLM)."""
    q = normalize_query_text(question)

    if not q:
        return "FACT"

    if any(hint in q for hint in _SUMMARY_HINTS):
        return "SUMMARY"

    if any(hint in q for hint in _LIST_HINTS):
        return "LIST"

    if any(hint in q for hint in _COMPARISON_HINTS):
        return "COMPARISON"

    if q.count("?") >= 2 or _MULTI_PART_PATTERN.search(q):
        return "MULTI_PART"

    if any(hint in q for hint in _EXPLANATION_HINTS):
        return "EXPLANATION"

    return "FACT"


# ---------------------------------------------------------------------------
# General Document Intent Recognition
# ---------------------------------------------------------------------------

_INTENT_KEYWORDS = {
    "identity": ["name", "my name", "who is", "applicant", "candidate", "author", "person", "full name", "employee name", "whose resume"],
    "skills": ["skill", "skills", "technologies", "tech stack", "programming", "tools", "competencies", "languages"],
    "education": ["education", "study", "degree", "college", "university", "school", "gpa", "bachelor", "master", "academic"],
    "experience": ["experience", "work", "job", "career", "employment", "role", "designation", "position", "company", "worked"],
    "dates": ["date", "joining date", "start date", "end date", "when", "year", "timeline", "duration", "period"],
    "compensation": ["salary", "compensation", "pay", "wage", "income", "ctc", "stipend", "monthly salary", "annual salary"],
    "financial": ["price", "cost", "rate", "fee", "amount", "total", "budget", "invoice"],
    "policy": ["policy", "leave", "casual leave", "sick leave", "annual leave", "working hours", "vacation", "rules", "guidelines", "conduct"],
    "contact": ["email", "phone", "contact", "mobile", "address", "location", "telephone"],
    "identifier": ["id", "employee id", "emp id", "po number", "crm", "code", "model", "invoice number", "tracking"],
    "product": ["product", "products", "inventory", "item", "items", "quantity", "stock", "material"],
}


def detect_query_intents(question: str) -> list[str]:
    """Detect general query intent categories without hardcoding specific names."""
    q = normalize_query_text(question)
    detected = []

    for intent, hints in _INTENT_KEYWORDS.items():
        for hint in hints:
            if re.search(r"\b" + re.escape(hint) + r"\b", q):
                if intent not in detected:
                    detected.append(intent)
                break

    return detected


# ---------------------------------------------------------------------------
# Keyword Extraction
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "what", "which", "who",
    "whom", "whose", "when", "where", "how", "why", "do", "does", "did",
    "has", "have", "had", "of", "in", "on", "at", "for", "to", "from",
    "with", "by", "and", "or", "but", "not", "it", "its", "this", "that",
    "these", "those", "there", "their", "they", "he", "she", "his", "her",
    "him", "you", "your", "i", "me", "my", "we", "us", "our", "be", "been",
    "being", "about", "can", "could", "would", "should", "will", "shall",
    "may", "might", "please", "tell", "say", "give", "find", "show", "need",
    "want", "like", "list", "any", "all", "some", "each", "every", "up",
    "down", "out", "off", "into", "over", "under", "between", "than", "also",
    "then", "so", "if", "as", "because", "via", "per", "etc", "within",
    "during", "without", "get", "know", "see", "using", "used", "document",
    "file", "uploaded", "resume", "pdf",
}


def extract_keywords(question: str, max_keywords: int = 8) -> list[str]:
    """Extract key single words and discriminative bigrams."""
    q = normalize_query_text(question)

    tokens = [t for t in q.split() if t not in _STOPWORDS and len(t) > 1]
    tokens = [t for t in tokens if not t.isdigit() or len(t) > 3]

    # Include normalized singular forms if present in plural map
    expanded_tokens = []
    for t in tokens:
        expanded_tokens.append(t)
        if t in _SINGULAR_PLURAL_MAP:
            expanded_tokens.append(_SINGULAR_PLURAL_MAP[t])

    # Bigrams
    bigrams = []
    for i in range(len(tokens) - 1):
        if tokens[i] not in _STOPWORDS and tokens[i+1] not in _STOPWORDS:
            bigrams.append(f"{tokens[i]} {tokens[i+1]}")

    results = []
    for phrase in bigrams + expanded_tokens:
        if phrase not in results:
            results.append(phrase)
        if len(results) >= max_keywords:
            break

    return results


# ---------------------------------------------------------------------------
# Entity Extraction (IDs, Codes, Dates, Amounts, Phones, Emails, URLs)
# ---------------------------------------------------------------------------

_ENTITY_PATTERNS = [
    ("email", re.compile(r"[\w.+-]+@[\w.-]+\.\w{2,}")),
    ("phone", re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")),
    ("amount", re.compile(r"[\$₹€£]\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*\s?(?:usd|inr|eur|dollars|rupees)\b", re.I)),
    ("percent", re.compile(r"\d+(?:\.\d+)?\s?%")),
    ("date", re.compile(r"\b\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}\b|\b\d{1,2}\s(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s\d{2,4}\b|\b\d{4}-\d{4}\b", re.I)),
    ("code", re.compile(r"\b[A-Z]{2,}[-\s]?\d{2,}\b|\bEMP\d+\b|\bPO-\d{4}-\d+\b|\bCRM-\d+\b|\bINV-\d+\b|\b[A-Z0-9]{3,}-[A-Z0-9-]+\b")),
]


def extract_entities(question: str) -> list[tuple[str, str]]:
    """Extract specific structured entities (e.g. EMP-1042, PO-2026-0042, dates, amounts)."""
    entities = []
    seen = set()

    for entity_type, pattern in _ENTITY_PATTERNS:
        for match in pattern.findall(question):
            val = match.strip()
            key = val.lower()
            if key and key not in seen:
                seen.add(key)
                entities.append((entity_type, val))

    return entities


# ---------------------------------------------------------------------------
# Query Expansion (Local Synonyms, Multi-Part Decomposition)
# ---------------------------------------------------------------------------

_SYNONYM_MAP = {
    "identity": ["candidate applicant person author profile identity name", "candidate full name applicant identity"],
    "name": ["candidate applicant person author profile identity name", "candidate full name applicant identity"],
    "salary": ["salary pay compensation wage income ctc monthly annual", "monthly salary compensation"],
    "skills": ["skills technologies expertise programming tools tech stack", "programming languages frameworks"],
    "experience": ["experience work history employment background career role", "work experience projects"],
    "working hours": ["working hours work hours office hours timings schedule", "business hours office schedule"],
    "leave": ["leave vacation time off annual casual sick leave holidays", "casual leave sick leave policy"],
    "policy": ["policy rules guidelines regulation code of conduct", "company policy rules"],
    "benefits": ["benefits perks allowances health insurance coverage", "health insurance medical coverage"],
    "requirements": ["requirements prerequisites criteria qualifications", "job requirements criteria"],
    "department": ["department division unit team", "functional department"],
    "employee id": ["employee id emp id emp no id number badge id", "employee id number"],
    "identifier": ["employee id emp id emp no po number crm code", "identification code number"],
    "address": ["address location headquarters office address", "company location address"],
    "products": ["products items materials parts goods inventory", "product items pricing"],
    "price": ["price cost rate value amount total", "product price cost rate"],
    "project": ["project initiative program assignment", "software projects"],
    "education": ["education degree qualification academic college university", "academic degree college"],
    "contact": ["contact phone email telephone mobile address", "contact details email phone"],
}


def expand_query(question: str, keywords: list[str] | None = None, entities: list[tuple[str, str]] | None = None) -> list[str]:
    """Build query expansion variants for retrieval (pure local, zero LLM)."""
    if keywords is None:
        keywords = extract_keywords(question)
    if entities is None:
        entities = extract_entities(question)

    variants = []

    # 1. Raw entity strings (highest precision for exact matches)
    if entities:
        for _entity_type, value in entities:
            if value not in variants:
                variants.append(value)

    # 2. Multi-part / multi-intent decomposition
    if " and " in question.lower() or " & " in question:
        parts = re.split(r"\s+(?:and|&)\s+", question, flags=re.IGNORECASE)
        for p in parts:
            p_clean = strip_question_boilerplate(p)
            if p_clean and len(p_clean) > 3 and p_clean not in variants:
                variants.append(p_clean)
                # Also add intent expansion for each sub-part
                sub_intents = detect_query_intents(p_clean)
                for si in sub_intents:
                    if si in _SYNONYM_MAP:
                        syn = _SYNONYM_MAP[si][0]
                        if syn not in variants:
                            variants.append(syn)

    # 3. General intent synonyms
    intents = detect_query_intents(question)
    for intent in intents:
        if intent in _SYNONYM_MAP:
            for syn in _SYNONYM_MAP[intent]:
                if syn not in variants:
                    variants.append(syn)

    # 4. Keyword-level synonyms
    for kw in keywords:
        for canonical, syns in _SYNONYM_MAP.items():
            if kw == canonical or kw in syns or canonical in kw:
                alt = [s for s in syns if s != kw]
                if alt:
                    joined = " OR ".join(alt[:3])
                    if joined not in variants:
                        variants.append(joined)
                break

    return variants[:6]


# ---------------------------------------------------------------------------
# Broad Question Detection
# ---------------------------------------------------------------------------

_BROAD_HINTS = _SUMMARY_HINTS + (
    "list all",
    "list the",
    "all the skills",
    "all the requirements",
    "all the policies",
    "what are all",
    "give me all",
    "tell me everything",
    "every skill",
    "every requirement",
    "complete profile",
    "full details",
    "all the important",
)


def is_broad_question(question: str) -> bool:
    q = normalize_query_text(question)
    return any(hint in q for hint in _BROAD_HINTS)


# ---------------------------------------------------------------------------
# Follow-Up Question Resolution
# ---------------------------------------------------------------------------

_FOLLOWUP_PATTERN = re.compile(
    r"^\s*(?:and|what about|how about|also|then|what is|what are|when did|"
    r"where is|where are|who is|who are|does|did|is|are|can|could|"
    r"how much|how many|what's)\b",
    re.I,
)

_PRONOUN_PATTERN = re.compile(
    r"\b(he|she|his|her|hers|him|its|it|their|theirs|they|them|that|"
    r"this|those|these|the above|the employee|the candidate|the person|"
    r"that company|that project)\b",
    re.I,
)


def looks_like_follow_up(question: str) -> bool:
    if not question:
        return False
    if _FOLLOWUP_PATTERN.match(question):
        return True
    if _PRONOUN_PATTERN.search(question):
        return True
    return False


def resolve_follow_up(question: str, chat_history: list[dict] | None) -> str:
    """Resolve follow-up references using recent chat history for retrieval."""
    if not chat_history or not looks_like_follow_up(question):
        return question

    prior_user = None
    for message in reversed(chat_history):
        if message.get("role") == "user":
            prior_user = message.get("content", "").strip()
            if prior_user:
                break

    if not prior_user:
        return question

    return f"{prior_user} — follow-up: {question}"
