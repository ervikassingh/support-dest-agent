from rag.chunking import chunk_markdown, document_title, embed_prefix


def test_chunks_follow_headings_and_do_not_cross_them():
    markdown = """<!-- page:1 -->
# Refunds

## Window

A refund request must arrive within 30 days of the delivery date.

## Shipping fees

Shipping fees are non-refundable unless the store caused the return.
"""
    chunks = chunk_markdown(markdown, size=40, overlap=0)
    paths = [chunk.header_path for chunk in chunks]
    assert "Refunds > Window" in paths
    assert "Refunds > Shipping fees" in paths
    window = next(chunk for chunk in chunks if chunk.header_path == "Refunds > Window")
    assert "Shipping fees" not in window.content
    assert window.page_start == 1
    assert document_title(markdown, "fallback") == "Refunds"
    prefix = embed_prefix("Refunds", window)
    assert prefix.startswith("[Refunds] › Refunds > Window (p. 1)")


def test_page_marker_moves_with_the_section():
    markdown = """<!-- page:1 -->
# Privacy

## Data we store

The store keeps the customer name.

<!-- page:2 -->
## Invoices

Invoices are retained for 7 years.
"""
    chunks = chunk_markdown(markdown, size=200, overlap=0)
    invoices = next(chunk for chunk in chunks if chunk.header_path == "Privacy > Invoices")
    assert invoices.page_start == 2
    assert invoices.page_end == 2
