"""Ranking metrics. Flags are 1 when a retrieved row is relevant, in rank order."""

from __future__ import annotations

import math


def _dcg(flags: list[int]) -> float:
    return sum(flag / math.log2(index + 2) for index, flag in enumerate(flags))


def hit_at(flags: list[int], k: int) -> float:
    return 1.0 if any(flags[:k]) else 0.0


def precision_at(flags: list[int], k: int) -> float:
    if k <= 0:
        return 0.0
    return sum(flags[:k]) / k


def recall_at(flags: list[int], k: int, n_relevant: int) -> float:
    if n_relevant <= 0:
        return 0.0
    return sum(flags[:k]) / n_relevant


def mrr_at(flags: list[int], k: int) -> float:
    for index, flag in enumerate(flags[:k], start=1):
        if flag:
            return 1.0 / index
    return 0.0


def average_precision_at(flags: list[int], k: int, n_relevant: int) -> float:
    """MAP's per-query term. Divides by the number of relevant items, not by k."""
    if n_relevant <= 0:
        return 0.0
    hits = 0
    total = 0.0
    for index, flag in enumerate(flags[:k], start=1):
        if flag:
            hits += 1
            total += hits / index
    return total / n_relevant


def ndcg_at(flags: list[int], k: int, n_relevant: int) -> float:
    ideal = min(k, n_relevant)
    if ideal <= 0:
        return 0.0
    idcg = _dcg([1] * ideal)
    if idcg == 0:
        return 0.0
    return _dcg(flags[:k]) / idcg


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def relevance_flags(documents: list[dict], labels: list[dict], k: int) -> list[int]:
    """One point per label. A later chunk that repeats a label already hit scores 0."""
    flags: list[int] = []
    seen: set[int] = set()
    for document in documents[:k]:
        matched = None
        for index, label in enumerate(labels):
            if index in seen:
                continue
            title = (document.get("title") or "").strip().lower()
            path = (document.get("header_path") or "").strip().lower()
            label_title = label["title"].strip().lower()
            label_path = label["header_path"].strip().lower()
            title_ok = title == label_title
            path_ok = path == label_path or path.startswith(label_path + " >")
            if title_ok and path_ok:
                matched = index
                break
        if matched is None:
            flags.append(0)
        else:
            seen.add(matched)
            flags.append(1)
    return flags
