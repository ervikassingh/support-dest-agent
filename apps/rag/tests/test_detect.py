from rag.detect import google_export_url


def test_google_docs_sheets_and_slides_export_as_pdf():
    assert google_export_url(
        "https://docs.google.com/document/d/abc123/edit?usp=sharing"
    ) == "https://docs.google.com/document/d/abc123/export?format=pdf"
    assert google_export_url(
        "https://docs.google.com/spreadsheets/d/sheet1/edit"
    ) == "https://docs.google.com/spreadsheets/d/sheet1/export?format=pdf"
    assert google_export_url(
        "https://docs.google.com/presentation/d/deck1/edit"
    ) == "https://docs.google.com/presentation/d/deck1/export?format=pdf"
    assert google_export_url("https://example.com/help") is None
