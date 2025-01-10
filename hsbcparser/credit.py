from __future__ import annotations

import re
import subprocess
from collections.abc import Iterator
from pathlib import Path


from .common import parse_date, parse_money, Transaction


def inputs(data: Path) -> list[Path]:
    # TODO use get_inputs form hpi?
    res = sorted(data.glob('*.pdf'))
    assert len(res) > 0
    return res


def _extract_candidates(text: str) -> Iterator[str]:
    # TODO extract interest too? from "total interest charged on this statement"
    for line in text.splitlines():
        line = line.lstrip()  # sometime contains space in front
        if not re.match(r'\d\d \w\w\w \d\d', line):
            continue
        yield line


def extract_transactions(pdf: Path) -> Iterator[Transaction]:
    text = subprocess.check_output([
        'pdftotext',
        '-q',  # craps with ' Invalid Font Weight' warning otherwise
        '-layout',  # without -layout it seems to split the table in multiple lines in weird way
        pdf,
        '-',  # output to stdout
    ], text=True)

    candidates = list(_extract_candidates(text))
    assert len(candidates) > 0, pdf  # each statement should have some transactions?

    for line in candidates:
        split = line.split()
        dt_received = parse_date(' '.join(split[:3]))
        dt_transaction = parse_date(' '.join(split[3:6]))
        details = ' '.join(split[6:-1])
        amount_s = split[-1]

        if amount_s.endswith('CR'):  # card credited
            amount_ = amount_s.removesuffix('CR')
        else:
            amount_ = '-' + amount_s

        amount = parse_money(amount_)
        assert amount is not None

        yield Transaction(
            dt=dt_transaction,
            details=details,
            change_str=amount,
            balance_str=None,
        )


def all_transactions(data: Path) -> Iterator[Transaction]:
    balance_pennies = 0
    for pdf in inputs(data):
        for t in extract_transactions(pdf):
            # TODO check balances? need to extract from statements though
            yield t


if __name__ == '__main__':
    DATA = Path('TODO')
    for t in all_transactions(DATA):
        print(t)
