import re
import uuid
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


# Project paths
BASE_DIR = Path(__file__).resolve().parent
VECTOR_DB_DIR = BASE_DIR / "vectorstore"

VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)


# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(
    path=str(VECTOR_DB_DIR)
)

collection = chroma_client.get_or_create_collection(
    name="gapfinder_documents"
)


# Load local embedding model
print("Loading embedding model...")

embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

print("Embedding model loaded successfully!")


def split_into_chunks(text, chunk_size=900, overlap=150):
    """Split text into smaller overlapping chunks."""

    chunks = []

    start = 0

    while start < len(text):
        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


def index_document(document_id, filename, extracted_text):
    """Create embeddings and store PDF chunks in ChromaDB."""

    if not extracted_text.strip():
        raise ValueError("Document contains no text.")

    # Remove previous index entries for this document
    existing = collection.get(
        where={"document_id": document_id}
    )

    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    # Separate text by page
    page_sections = re.split(
    r"(?=Page \d+\n)",
    extracted_text
)

    ids = []
    documents = []
    metadatas = []

    for section in page_sections:

        section = section.strip()

        if not section:
            continue

        match = re.match(r"Page (\d+)\n", section)

        if match:
            page_number = int(match.group(1))
            page_text = section[match.end():].strip()
        else:
            page_number = 1
            page_text = section

        if not page_text:
            continue

        chunks = split_into_chunks(page_text)

        for chunk_number, chunk in enumerate(chunks):

            ids.append(str(uuid.uuid4()))

            documents.append(chunk)

            metadatas.append({
                "document_id": document_id,
                "filename": filename,
                "page": page_number,
                "chunk": chunk_number
            })

    if not documents:
        raise ValueError("No text chunks could be created.")

    # Generate local embeddings
    embeddings = embedding_model.encode(
        documents,
        normalize_embeddings=True
    ).tolist()

    # Save in ChromaDB
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )

    return {
        "document_id": document_id,
        "filename": filename,
        "total_chunks": len(documents),
        "message": "Document indexed successfully."
    }


def ensure_existing_documents_indexed(uploads_dir):
    """Index persisted uploads that are missing from the vector store."""
    indexed_documents = 0

    for text_file in uploads_dir.glob("*.txt"):
        document_id = text_file.stem
        existing = collection.get(
            where={"document_id": document_id},
            limit=1
        )

        if existing["ids"]:
            continue

        index_document(
            document_id=document_id,
            filename=f"{document_id}.pdf",
            extracted_text=text_file.read_text(encoding="utf-8")
        )
        indexed_documents += 1

    return indexed_documents


def search_documents(question, document_id=None, top_k=5):
    """Find relevant PDF chunks for a question."""

    if not question.strip():
        raise ValueError("Search question cannot be empty.")

    if collection.count() == 0:
        return []

    query_embedding = embedding_model.encode(
        [question],
        normalize_embeddings=True
    ).tolist()

    search_arguments = {
        "query_embeddings": query_embedding,
        "n_results": min(top_k, collection.count()),
        "include": ["documents", "metadatas", "distances"]
    }

    if document_id:
        search_arguments["where"] = {
            "document_id": document_id
        }

    results = collection.query(**search_arguments)

    matches = []

    for index, chunk in enumerate(results["documents"][0]):

        metadata = results["metadatas"][0][index]
        distance = results["distances"][0][index]

        matches.append({
            "text": chunk,
            "filename": metadata["filename"],
            "document_id": metadata["document_id"],
            "page": metadata["page"],
            "chunk": metadata["chunk"],
            "distance": round(float(distance), 4)
        })

    return matches