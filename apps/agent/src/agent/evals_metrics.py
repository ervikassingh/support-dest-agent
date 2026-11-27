"""pass@k and pass^k for a fixed sample of n runs."""

from __future__ import annotations

from math import comb


def pass_at_k(n: int, correct: int, k: int) -> float:
    """Probability that at least one of k draws from n samples is correct."""
    if k <= 0 or n <= 0 or k > n:
        return 0.0
    if n - correct < k:
        return 1.0
    return 1.0 - comb(n - correct, k) / comb(n, k)


def pass_hat_k(n: int, correct: int, k: int) -> float:
    """pass^k: probability that all k draws are correct."""
    if k <= 0 or n <= 0 or k > n or correct < k:
        return 0.0
    return comb(correct, k) / comb(n, k)
