import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors

from app.rag_service import search_documents

ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_FILE)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
FALLBACK_MODEL = "gemini-3.5-flash-lite"


def get_client():
    api_key = os.getenv("GEMINI_API_KEY") or API_KEY
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def ask_gemini(question: str, document_id: str = None) -> dict:
    client = get_client()
    if not client:
        raise ValueError("Gemini API key is not configured.")
    
    current_model = os.getenv("GEMINI_MODEL", MODEL)

    if not question.strip():
        raise ValueError("Please enter a question.")

    # Step 1: Retrieve relevant chunks from ChromaDB
    matches = search_documents(
        question=question,
        document_id=document_id,
        top_k=5
    )

    if not matches:
        raise ValueError(
            "No relevant study material found. Please upload a PDF first."
        )

    # Step 2: Build context and source references
    context_parts = []
    sources = []

    for match in matches:
        context_parts.append(
            f"""
Source: {match['filename']}
Page: {match['page']}
Content:
{match['text']}
"""
        )

        source = {
            "filename": match["filename"],
            "page": match["page"]
        }

        if source not in sources:
            sources.append(source)

    context = "\n\n".join(context_parts)

    # Step 3: Ask Gemini using retrieved PDF content
    prompt = f"""
You are GapFinder AI, an educational study assistant.

Answer the student's question using ONLY the study material
provided below.

RULES:
1. Do not use outside knowledge.
2. Do not invent facts.
3. Explain in simple, student-friendly language.
4. If the material does not contain the answer, clearly say so.
5. Do not pretend that unsupported information is in the PDF.
6. Keep the answer relevant to the student's question.

UPLOADED STUDY MATERIAL:
{context}

STUDENT QUESTION:
{question}

Provide a clear and helpful answer.
"""

    try:
        response = client.models.generate_content(
            model=current_model,
            contents=prompt
        )
    except errors.APIError as error:
        if error.code not in (429, 503) or current_model == FALLBACK_MODEL:
            raise

        print(
            f"Gemini model {current_model} returned HTTP {error.code}; "
            f"retrying with {FALLBACK_MODEL}."
        )
        response = client.models.generate_content(
            model=FALLBACK_MODEL,
            contents=prompt
        )

    answer = response.text

    if not answer:
        raise ValueError("Gemini returned an empty response.")

    # Step 4: Return answer and source references
    return {
        "answer": answer,
        "sources": sources,
        "retrieved_chunks": len(matches)
    }