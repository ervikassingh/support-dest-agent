import pytest

from rag.ingest import assert_public_http_url, safe_filename


def test_filename_cannot_leave_the_uploads_dir():
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("..\\..\\windows\\system.ini") == "system.ini"
    assert safe_filename("..") == "upload"
    assert safe_filename("returns.md") == "returns.md"


def test_download_refuses_non_public_hosts():
    for url in (
        "http://127.0.0.1/latest",
        "http://localhost/health",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/admin",
        "file:///etc/passwd",
    ):
        with pytest.raises(RuntimeError):
            assert_public_http_url(url)
