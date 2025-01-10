from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date


@dataclass
class Transaction:
    dt: date
    """
    HSBC only has date, not time
    """

    details: str

    change_str: str | None
    """
    Can be None if it's a pure balance transaction
    """

    balance_str: str | None
    """
    Balance after current transaction
    """

    # todo maybe add transaction number? to make it easier to sort?

    def __post_init__(self) -> None:
        assert not (self.change_str is None and self.balance_str is None)

        if self.change_str is not None:
            float(self.change_str)  # shouldn't throw

        if self.balance_str is not None:
            float(self.balance_str)  # shouldn't throw


def parse_date(s: str) -> date:
    return datetime.strptime(s, '%d %b %y').date()


def is_empty(s: str) -> bool:
    return len(s) == 0


def parse_money(x: str) -> None | str:
    """
    Remove ',' separators and check that amount is actually a number
    """
    if is_empty(x):
        return None

    x = x.replace(',', '')
    float(x)  # sanity check, but we want preserve str to avoid floating point stuff?
    return x
