"""Classic ELO rating math."""

from config import ELO_K


def expected_score(rating_a: int, rating_b: int) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def update_ratings(winner: int, loser: int, k: int = ELO_K):
    """Return (new_winner, new_loser, delta) after a decisive game."""
    exp_w = expected_score(winner, loser)
    delta = round(k * (1 - exp_w))
    return winner + delta, loser - delta, delta
