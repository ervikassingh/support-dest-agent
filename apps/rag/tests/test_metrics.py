from rag.evals.metrics import (
    average_precision_at,
    hit_at,
    mrr_at,
    ndcg_at,
    precision_at,
    recall_at,
    relevance_flags,
)
from rag.retrieve import canonicalize, reciprocal_rank_fusion


def test_ranking_metrics():
    flags = [1, 0, 1, 0, 0]
    assert hit_at(flags, 5) == 1
    assert precision_at(flags, 5) == 0.4
    assert recall_at(flags, 5, 2) == 1
    assert mrr_at(flags, 10) == 1
    assert average_precision_at(flags, 10, 2) == (1 + 2 / 3) / 2
    assert 0.9 < ndcg_at(flags, 10, 2) < 0.93
    assert hit_at([0, 0], 5) == 0
    assert mrr_at([0, 0, 1], 2) == 0


def test_relevance_flags_match_title_and_header_once():
    documents = [
        {"title": "Refunds", "header_path": "Refunds > Window"},
        {"title": "Refunds", "header_path": "Refunds > Window"},
        {"title": "Shipping", "header_path": "Shipping > Express"},
    ]
    labels = [
        {"title": "Refunds", "header_path": "Refunds > Window"},
        {"title": "Shipping", "header_path": "Shipping > Standard"},
    ]
    assert relevance_flags(documents, labels, 10) == [1, 0, 0]


def test_fusion_and_version_collapse():
    rows = [
        {"id": "old", "content_hash": "h", "version": 1},
        {"id": "new", "content_hash": "h", "version": 2},
        {"id": "other", "content_hash": "o", "version": 1},
    ]
    fused = reciprocal_rank_fusion(
        canonicalize(rows, [["old", "other"], ["new"]]),
        k=60,
    )
    assert fused[0][0] == "new"
    assert all(item != "old" for item, _score in fused)
