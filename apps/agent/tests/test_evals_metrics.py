from agent.evals_metrics import pass_at_k, pass_hat_k


def test_pass_at_and_pass_hat():
    assert pass_at_k(5, 5, 1) == 1
    assert pass_hat_k(5, 5, 5) == 1
    assert pass_at_k(5, 1, 1) == 0.2
    assert pass_at_k(5, 1, 5) == 1
    assert pass_hat_k(5, 1, 5) == 0
    assert pass_at_k(5, 0, 1) == 0
