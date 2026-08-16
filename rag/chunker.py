def chunk_text(text, chunk_size=1000, overlap=200):

    text = text.strip()

    if not text:
        return []

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end]

        if chunk.strip():
            chunks.append(chunk.strip())

        start += chunk_size - overlap

    return chunks


def create_chunks(pages, source):

    all_chunks = []

    for page_data in pages:

        text = page_data["text"]
        page = page_data["page"]

        chunks = chunk_text(text)

        for chunk in chunks:

            all_chunks.append({
                "text": chunk,
                "metadata": {
                    "source": source,
                    "page": page
                }
            })

    return all_chunks