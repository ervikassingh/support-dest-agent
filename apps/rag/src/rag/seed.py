"""Write the seed policy corpus and the golden questions that point at it."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from docx import Document
from fpdf import FPDF

_REPO = Path(__file__).resolve().parents[4]
SEED_DIR = _REPO / "docs" / "seed"
GOLDEN_PATH = Path(__file__).resolve().parents[2] / "evals" / "golden.json"

# heading, body, question. Bodies are the facts the evals grade against.
POLICIES: list[dict] = [
    {
        "slug": "refunds",
        "title": "Refunds",
        "filename": "refunds.md",
        "format": "md",
        "sections": [
            (
                "Window",
                "A refund request must arrive within 30 days of the delivery date.",
                "How long do I have to request a refund after delivery?",
            ),
            (
                "Digital goods",
                "Digital goods can be refunded within 14 days if the file was never downloaded.",
                "Can I refund a digital download, and how long do I have?",
            ),
            (
                "Payment method",
                "Refunds are sent to the original payment method. Store credit is offered only when that method fails.",
                "Where is a refund sent, and when is store credit used?",
            ),
            (
                "Shipping fees",
                "Shipping fees are non-refundable unless the store caused the return.",
                "Do I get the shipping fee back when I return an item?",
            ),
        ],
    },
    {
        "slug": "shipping",
        "title": "Shipping",
        "filename": "shipping.txt",
        "format": "txt",
        "sections": [
            (
                "Standard",
                "Standard shipping takes 5 to 7 business days.",
                "How long does standard shipping take?",
            ),
            (
                "Express",
                "Express shipping takes 2 business days and is unavailable for P.O. boxes.",
                "How fast is express shipping, and can it go to a P.O. box?",
            ),
            (
                "Free shipping",
                "Orders over $50 ship free with standard shipping.",
                "When is standard shipping free?",
            ),
        ],
    },
    {
        "slug": "returns",
        "title": "Returns",
        "filename": "returns.html",
        "format": "html",
        "sections": [
            (
                "Condition",
                "Returned items must be unworn and include the original tags.",
                "What condition does an item have to be in to be returned?",
            ),
            (
                "Label",
                "The return label is generated from the customer account page.",
                "Where do I get a return label?",
            ),
            (
                "Timeline",
                "The refund is issued 5 business days after the warehouse scans the return.",
                "How soon is a refund issued after the warehouse scans a return?",
            ),
        ],
    },
    {
        "slug": "warranty",
        "title": "Warranty",
        "filename": "warranty.docx",
        "format": "docx",
        "sections": [
            (
                "Coverage",
                "Hardware includes a 1 year warranty for manufacturer defects.",
                "How long is the hardware warranty and what does it cover?",
            ),
            (
                "Exclusions",
                "Accidental damage is not covered by the warranty.",
                "Does the warranty cover accidental damage?",
            ),
            (
                "Claims",
                "A warranty claim needs the order id and a short description of the defect.",
                "What do I need to submit a warranty claim?",
            ),
        ],
    },
    {
        "slug": "privacy",
        "title": "Privacy",
        "filename": "privacy.pdf",
        "format": "pdf",
        "sections": [
            (
                "Data we store",
                "The store keeps the customer name, email address, and order history.",
                "What customer data does the store keep?",
            ),
            (
                "Selling data",
                "Personal data is never sold to third parties.",
                "Does the store sell personal data?",
            ),
            (
                "Deletion",
                "Account deletion requests go to privacy@northwind.example.",
                "How do I ask for my account to be deleted?",
            ),
            (
                "Invoices",
                "Invoices are retained for 7 years.",
                "How long are invoices kept?",
            ),
        ],
    },
    {
        "slug": "payments",
        "title": "Payments",
        "filename": "payments.md",
        "format": "md",
        "sections": [
            (
                "Cards",
                "Accepted cards are Visa, Mastercard, and American Express.",
                "Which cards are accepted?",
            ),
            (
                "Cash",
                "Cash on delivery is not available.",
                "Can I pay cash on delivery?",
            ),
            (
                "Retries",
                "A failed payment is retried 3 times over 24 hours.",
                "What happens when a card payment fails?",
            ),
        ],
    },
    {
        "slug": "account",
        "title": "Account",
        "filename": "account.txt",
        "format": "txt",
        "sections": [
            (
                "Email",
                "Each email address can belong to only one account.",
                "Can two accounts share an email address?",
            ),
            (
                "Password reset",
                "A password reset link expires after 30 minutes.",
                "How long is a password reset link valid?",
            ),
            (
                "Closure",
                "Closing an account keeps order history for 7 years.",
                "What happens to order history when I close my account?",
            ),
        ],
    },
]


def _markdown(policy: dict) -> str:
    lines = [f"# {policy['title']}", ""]
    for heading, body, _question in policy["sections"]:
        lines.extend([f"## {heading}", "", body, ""])
    return "\n".join(lines).strip() + "\n"


def _html(policy: dict) -> str:
    parts = [
        "<!DOCTYPE html>",
        "<html>",
        f"<head><title>{policy['title']}</title></head>",
        "<body>",
        f"<h1>{policy['title']}</h1>",
    ]
    for heading, body, _question in policy["sections"]:
        parts.append(f"<h2>{heading}</h2>")
        parts.append(f"<p>{body}</p>")
    parts.extend(["</body>", "</html>", ""])
    return "\n".join(parts)


def _docx(policy: dict, path: Path) -> None:
    document = Document()
    document.add_heading(policy["title"], level=1)
    for index, (heading, body, _question) in enumerate(policy["sections"]):
        if index:
            document.add_page_break()
        document.add_heading(heading, level=2)
        document.add_paragraph(body)
    document.save(path)


def _pdf(policy: dict, path: Path) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=16)
    pdf.multi_cell(0, 10, f"# {policy['title']}")
    pdf.ln(2)
    pdf.set_font("Helvetica", size=12)
    for index, (heading, body, _question) in enumerate(policy["sections"]):
        if index:
            pdf.add_page()
        pdf.multi_cell(0, 8, f"## {heading}")
        pdf.ln(1)
        pdf.multi_cell(0, 8, body)
        pdf.ln(2)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


def golden_cases() -> list[dict]:
    cases = []
    for policy in POLICIES:
        for heading, body, question in policy["sections"]:
            slug = heading.lower().replace(" ", "-")
            cases.append(
                {
                    "id": f"{policy['slug']}-{slug}",
                    "question": question,
                    "relevant": [
                        {
                            "title": policy["title"],
                            "header_path": f"{policy['title']} > {heading}",
                        }
                    ],
                    "reference_answer": body,
                }
            )
    return cases


def write_seed_files() -> list[Path]:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for policy in POLICIES:
        path = SEED_DIR / policy["filename"]
        kind = policy["format"]
        if kind == "docx":
            _docx(policy, path)
        elif kind == "pdf":
            _pdf(policy, path)
        elif kind == "html":
            path.write_text(_html(policy))
        else:
            path.write_text(_markdown(policy))
        written.append(path)
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(golden_cases(), indent=2) + "\n")
    return written


async def ingest_seed() -> None:
    from rag.db import ensure_schema
    from rag.ingest import ingest_document, reserve_document

    await ensure_schema()
    for path in write_seed_files():
        reserved = await reserve_document(
            source_key=path.name,
            filename=path.name,
            source_uri=None,
        )
        Path(reserved["storage_path"]).write_bytes(path.read_bytes())
        await ingest_document(reserved["id"])
        print(f"ingested {path.name} -> {reserved['id']} v{reserved['version']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write docs/seed and apps/rag/evals/golden.json")
    parser.add_argument("--ingest", action="store_true", help="Also embed the seed files into ParadeDB")
    args = parser.parse_args()
    if args.ingest:
        asyncio.run(ingest_seed())
        return
    paths = write_seed_files()
    for path in paths:
        print(path)
    print(GOLDEN_PATH)
