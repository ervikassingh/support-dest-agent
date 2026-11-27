"""Regenerate a review copy of the golden set. Does not overwrite golden.json."""

from __future__ import annotations

import json

from rag.seed import GOLDEN_PATH, golden_cases


def main() -> None:
    """Ragas testset generation needs a live corpus and is review-only.

    The committed golden file is the curated set built from docs/seed.
    This command writes golden.generated.json beside it. Replace golden.json
    after you have read the generated questions.
    """
    destination = GOLDEN_PATH.with_name("golden.generated.json")
    generated = _try_ragas()
    if generated is None:
        generated = golden_cases()
        print("Ragas testset generation was not run. Wrote the curated questions for review.")
    destination.write_text(json.dumps(generated, indent=2) + "\n")
    print(destination)


def _try_ragas() -> list[dict] | None:
    try:
        from langchain_core.documents import Document
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.testset import TestsetGenerator

        from rag.seed import POLICIES, _markdown
        from rag.settings import get_settings
    except Exception as exc:  # noqa: BLE001
        print(f"Ragas imports unavailable ({exc}).")
        return None

    settings = get_settings()
    if not settings.openrouter_api_key:
        print("OPENROUTER_API_KEY is not set.")
        return None
    docs = [
        Document(page_content=_markdown(policy), metadata={"title": policy["title"]})
        for policy in POLICIES
        if policy["format"] in {"md", "txt"}
    ]
    chat = ChatOpenAI(
        model=settings.judge_model,
        temperature=0,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        dimensions=settings.embedding_dim,
    )
    try:
        generator = TestsetGenerator(
            llm=LangchainLLMWrapper(chat),
            embedding_model=LangchainEmbeddingsWrapper(embeddings),
        )
        dataset = generator.generate_with_langchain_docs(docs, testset_size=len(docs))
    except Exception as exc:  # noqa: BLE001
        print(f"Ragas generation failed ({exc}).")
        return None

    cases = []
    frame = dataset.to_pandas()
    for index, row in frame.iterrows():
        question = row.get("user_input") or row.get("question")
        reference = row.get("reference") or row.get("ground_truth")
        if not question:
            continue
        cases.append(
            {
                "id": f"generated-{index}",
                "question": question,
                "relevant": [],
                "reference_answer": reference,
                "note": "Label title and header_path before using this case in golden.json.",
            }
        )
    return cases or None
