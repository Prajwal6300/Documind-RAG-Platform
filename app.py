import os
import tempfile

import streamlit as st
from dotenv import load_dotenv

from rag.document_loader import load_document
from rag.chunker import create_chunks
from rag.vector_store import add_chunks
from rag.rag_pipeline import answer_question


load_dotenv()


st.set_page_config(
    page_title="DocuMind",
    page_icon="📚",
    layout="wide"
)


st.title("📚 DocuMind")
st.caption(
    "RAG Document Chatbot — Ask questions about your documents"
)


if "messages" not in st.session_state:
    st.session_state.messages = []


if "documents" not in st.session_state:
    st.session_state.documents = []


# Sidebar
with st.sidebar:

    st.header("📄 Documents")

    uploaded_files = st.file_uploader(
        "Upload documents",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True
    )

    if uploaded_files:

        for uploaded_file in uploaded_files:

            if uploaded_file.name not in st.session_state.documents:

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=os.path.splitext(
                        uploaded_file.name
                    )[1]
                ) as temp_file:

                    temp_file.write(
                        uploaded_file.getvalue()
                    )

                    temp_path = temp_file.name

                try:

                    pages = load_document(temp_path)

                    chunks = create_chunks(
                        pages,
                        uploaded_file.name
                    )

                    add_chunks(chunks)

                    st.session_state.documents.append(
                        uploaded_file.name
                    )

                    st.success(
                        f"Indexed {uploaded_file.name}"
                    )

                except Exception as e:

                    st.error(
                        f"Error: {e}"
                    )


    st.divider()

    if st.button("🗑️ Clear Chat"):

        st.session_state.messages = []

        st.rerun()


# Chat history

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )


# Chat input

question = st.chat_input(
    "Ask a question about your documents..."
)


if question:

    st.session_state.messages.append({
        "role": "user",
        "content": question
    })

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):

        with st.spinner("Searching documents..."):

            result = answer_question(
                question
            )

        st.markdown(
            result["answer"]
        )

        if result["sources"]:

            with st.expander("📚 Sources"):

                for source in result["sources"]:

                    source_name = source["source"]
                    page = source["page"]

                    if page:
                        st.write(
                            f"📄 {source_name} — Page {page}"
                        )
                    else:
                        st.write(
                            f"📄 {source_name}"
                        )

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"]
    })