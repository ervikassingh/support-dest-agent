from rag.chunking import chunk_markdown
from rag.parse import parse_file
from rag.seed import SEED_DIR, write_seed_files


def test_every_seed_format_keeps_its_sections():
    write_seed_files()
    expected = {
        "refunds.md": "Refunds > Window",
        "shipping.txt": "Shipping > Express",
        "returns.html": "Returns > Timeline",
        "warranty.docx": "Warranty > Exclusions",
        "privacy.pdf": "Privacy > Invoices",
    }
    kinds = {
        "refunds.md": "md",
        "shipping.txt": "txt",
        "returns.html": "html",
        "warranty.docx": "docx",
        "privacy.pdf": "pdf",
    }
    for filename, path_label in expected.items():
        chunks = chunk_markdown(parse_file(SEED_DIR / filename, kinds[filename]), size=200, overlap=0)
        paths = {chunk.header_path for chunk in chunks}
        assert path_label in paths, filename
