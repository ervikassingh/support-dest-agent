"""RAG HTTP skeleton: health + retrieve/answer stubs."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Support Desk RAG", version="0.1.0")


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class AnswerRequest(BaseModel):
    question: str


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "rag",
        "pipeline": "stub",
        "note": "Chunk/embed/hybrid/rerank not implemented yet.",
    }


@app.post("/retrieve")
async def retrieve(body: RetrieveRequest) -> dict[str, Any]:
    """Return empty placeholder chunks until the corpus pipeline exists."""
    return {
        "query": body.query,
        "documents": [],
        "citations": [],
        "stub": True,
    }


@app.post("/answer")
async def answer(body: AnswerRequest) -> dict[str, Any]:
    """Placeholder answer — refuses weakly rather than inventing policy text."""
    return {
        "question": body.question,
        "answer": (
            "Stub RAG: no policy documents indexed yet. "
            "Retrieval would refuse rather than guess once the corpus is loaded."
        ),
        "citations": [],
        "refused": True,
        "stub": True,
    }


def run() -> None:
    import uvicorn

    uvicorn.run("rag.main:app", host="0.0.0.0", port=8001, reload=False)


if __name__ == "__main__":
    run()
