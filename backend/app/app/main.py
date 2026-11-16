from contextlib import asynccontextmanager
import os
import uuid
from pathlib import Path
import fitz
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.genai import errors
from pydantic import BaseModel

from app.gemini_service import ask_gemini
from app.rag_service import (
    ensure_existing_documents_indexed,
    index_document,
    search_documents,
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_existing_documents_indexed(UPLOAD_DIR)
    yield


app = FastAPI(
    title="GapFinder AI",
    description="AI-powered Student Knowledge Gap Detection Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "application": "GapFinder AI",
        "message": "Welcome to GapFinder AI Backend!",
        "status": "running"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "backend": "connected",
        "application": "GapFinder AI"
    }


@app.get("/api/ai/status")
def ai_status():
    api_key = os.getenv("GEMINI_API_KEY")

    return {
        "provider": "Google Gemini",
        "configured": bool(api_key),
        "message": (
            "Gemini API key detected"
            if api_key
            else "Gemini API key not configured yet"
        )
    }


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Please select a PDF file."
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported."
        )

    content = await file.read()

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="File size must be less than 10 MB."
        )

    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid PDF."
        )

    try:
        pdf = fitz.open(stream=content, filetype="pdf")

        pages = []
        extracted_pages = []

        for page_number, page in enumerate(pdf, start=1):
            page_text = page.get_text("text").strip()

            pages.append({
                "page": page_number,
                "character_count": len(page_text)
            })

            extracted_pages.append(
                f"Page {page_number}\n{page_text}"
            )

        page_count = len(pdf)
        pdf.close()

        extracted_text = "\n\n".join(extracted_pages)

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not read this PDF. Please try another file."
        )

    if not extracted_text.strip():
        raise HTTPException(
            status_code=422,
            detail="No selectable text found. Scanned PDFs are not supported yet."
        )

    document_id = str(uuid.uuid4())

    pdf_path = UPLOAD_DIR / f"{document_id}.pdf"
    text_path = UPLOAD_DIR / f"{document_id}.txt"

    pdf_path.write_bytes(content)
    text_path.write_text(extracted_text, encoding="utf-8")
    index_result = index_document(
        document_id=document_id,
        filename=file.filename,
        extracted_text=extracted_text
    )

    return {
        "success": True,
        "document_id": document_id,
        "filename": file.filename,
        "page_count": page_count,
        "character_count": len(extracted_text),
        "preview": extracted_text[:3000],
        "indexed_chunks": index_result["total_chunks"],
        "message": "PDF uploaded and text extracted successfully."
    }


@app.get("/api/documents")
def list_documents():

    documents = []

    for text_file in UPLOAD_DIR.glob("*.txt"):
        document_id = text_file.stem
        pdf_path = UPLOAD_DIR / f"{document_id}.pdf"

        text = text_file.read_text(encoding="utf-8")

        documents.append({
            "document_id": document_id,
            "filename": pdf_path.name,
            "character_count": len(text)
        })

    return {
        "total_documents": len(documents),
        "documents": documents
    }

class GeminiQuestion(BaseModel):
    question: str
    document_id: str | None = None

@app.post("/api/ai/ask")
def ask_ai(data: GeminiQuestion):
    try:
        result = ask_gemini(
            question=data.question,
            document_id=data.document_id
        )

        return {
            "success": True,
            "question": data.question,
            "answer": result["answer"],
            "sources": result["sources"],
            "retrieved_chunks": result["retrieved_chunks"]
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except errors.APIError as error:
        print(f"Gemini API error ({error.code}): {error.message}")
        if error.code == 429:
            detail = "Gemini rate limit reached. Please try again shortly."
        elif error.code in (401, 403):
            detail = "Gemini rejected the API key or model access. Check your API key and Google AI Studio access."
        else:
            detail = "Gemini is temporarily busy. Please try again shortly."

        raise HTTPException(
            status_code=503,
            detail=detail
        )

    except Exception as error:
        print(f"AI Error ({type(error).__name__}): {error}")

        raise HTTPException(
            status_code=503,
            detail="AI service is temporarily unavailable. Please try again."
        )


class RAGSearchRequest(BaseModel):
    question: str
    document_id: str | None = None
    top_k: int = 5


@app.post("/api/rag/search")
def rag_search(data: RAGSearchRequest):

    try:
        if not data.question.strip():
            raise HTTPException(
                status_code=400,
                detail="Please enter a search question."
            )

        if not 1 <= data.top_k <= 10:
            raise HTTPException(
                status_code=400,
                detail="top_k must be between 1 and 10."
            )

        results = search_documents(
            question=data.question,
            document_id=data.document_id,
            top_k=data.top_k
        )

        return {
            "success": True,
            "question": data.question,
            "total_results": len(results),
            "results": results
        }

    except HTTPException:
        raise

    except Exception as error:
        print(f"RAG search error: {error}")

        raise HTTPException(
            status_code=500,
            detail="Document search failed."
        )