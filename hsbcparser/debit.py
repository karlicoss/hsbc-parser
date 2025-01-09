#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path

from more_itertools import consecutive_groups


def inputs(data: Path) -> list[Path]:
    # TODO use get_inputs form hpi?
    res = sorted(data.glob('*.pdf'))
    assert len(res) > 0
    return res


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


def _extract_tables(text: str) -> Iterator[list[str]]:
    """
    Takes pdftotext output and only extracts relevant lines that actually contain transaction information

    Returns a list[str] for each page of transactions
      (they have different table sizes so need to be processed separately)
    """
    table: list[str] | None = None
    for line in text.splitlines():
        lline = line.lower()
        if line.startswith('Date') and line.endswith('Balance'):
            # header starts new table
            assert table is None
            table = [line]
            continue
        elif 'balance carried forward' in lline:
            # this is last line of the table, terminate it
            assert table is not None, line
            table.append(line)
            yield table
            table = None  # reset
            continue
        else:
            if table is not None:
                # collect data when we're inside a table
                table.append(line)


def _cleanup_table(dirty_table: list[str]) -> list[list[str]]:
    """
    Clean up entries coming from _extract_tables

    Ensures that the result has exactly five columns (date/details/paid out/paid in/balance)
    """

    rowlen = max(len(line) for line in dirty_table)
    for i in range(len(dirty_table)):
        dirty_table[i] = dirty_table[i] + ' ' * (rowlen - len(dirty_table[i]))  # pad to equal length

        # "balance brought forward" line sometimes contains this annoying dot which messes with column guessing
        # (likely pdftotext artifact)
        dirty_table[i] = dirty_table[i].replace('   .   ', '       ')

    dirty_table = [line for line in dirty_table if len(line.strip()) != 0]  # filter out empty lines
    dirty_table = [line for line in dirty_table if line.rstrip() != 'A']  # some statements contain line with letter A? seems like pdftotext artifact

    row_count = len(dirty_table)

    # thankfully pdftotext seems to keep content vertically aligned
    # so next step is to guess columns based on whitespace

    column_mask: list[int] = []  # indices of non-empty columns
    for i in range(rowlen):
        allempty = all(line[i] == ' ' for line in dirty_table)
        if not allempty:
            column_mask.append(i)

    table: list[list[str]] = [[] for _ in range(row_count)]
    for g in consecutive_groups(column_mask):
        lg = list(g)
        col_start = lg[0]
        col_end = lg[-1] + 1

        for li, line in enumerate(dirty_table):
            table[li].append(line[col_start: col_end])

    header = table[0]
    assert len(header) >= 5, header  # sanity check

    ## merge accidental columns
    table2: list[list[str]] = [[] for _ in range(row_count)]
    last = ''
    column: str | None = None
    for i, h in enumerate(header):
        h = h.strip()

        col_start = False
        if len(h) > 0:
            if h[0] == '£':
                # since 202404, hsbc started addint pound symbols to start of paid out/paid in/balance cols
                col_start = True
            elif h[0].isupper():
                if last != '£':
                    # if parsing paid out/paid in/balance, then capital letter is part of column
                    col_start = True
        last = h

        if not col_start:
            # merge to the previous column
            for j in range(len(table)):
                table2[j][-1] += ' ' + table[j][i]
        else:
            # otherwise start new column
            for j in range(len(table)):
                table2[j].append(table[j][i])
    table = table2
    ##

    header = table[0]

    header_xxx = [x.replace(' ', '').replace('£', '') for x in header]
    assert header_xxx == ['Date', 'Paymenttypeanddetails', 'Paidout', 'Paidin', 'Balance'], header_xxx

    data_entries = table[1:]

    data_entries = [
        [cell.strip() for cell in row]
        for row in data_entries
    ]
    return data_entries


def is_empty(s: str) -> bool:
    return len(s) == 0


def parse_money(x: str) -> None | str:
    """
    Remove , separators and check that amount is actually a number
    """
    if is_empty(x):
        return None
    x = x.replace(',', '')
    float(x)  # sanity check, but we want preserve str to avoid floating point stuff?
    return x


def extract_transactions(pdf: Path) -> Iterator[Transaction]:
    text = subprocess.check_output([
        'pdftotext',
        '-q',  # craps with ' Invalid Font Weight' warning otherwise
        '-layout',  # without -layout it seems to split the table in multiple lines in weird way
        pdf,
        '-',  # output to stdout
    ], text=True)

    dirty_tables: list[list[str]] = list(_extract_tables(text))
    assert len(dirty_tables) > 0, pdf  # just in case

    # merge all data entries into a single list
    data_entries: list[list[str]] = []
    for dirty in dirty_tables:
        data_entries.extend(_cleanup_table(dirty))


    cur_date: date | None = None
    cur_details: list[str] = []

    for row in data_entries:
        row_date, row_details, paidouts, paidins, balances = row
        if not is_empty(row_date):
            # if it has a date, keep it as 'current' date (there might be multiple entries for the same date)
            cur_date = datetime.strptime(row_date, '%d %b %y').date()

        cur_details.append(row_details)
        if is_empty(paidouts) and is_empty(paidins) and is_empty(balances):
            # that can happen if line only has transaction description
            continue

        # otherwise entry has some amount assigned to it, so verify and emit it
        assert cur_date is not None
        assert len(cur_details) > 0

        paidout = parse_money(paidouts)
        paidin  = parse_money(paidins)
        balance = parse_money(balances)

        details = '\n'.join(cur_details)
        cur_details.clear()

        change: str | None

        if re.search('BALANCE.*FORWARD', details):
            assert paidout is None and paidin is None and balance is not None
            change = None
        else:
            # balance can be None if multiple entries on the same line
            assert (paidout is None) ^ (paidin is None)  # only one should be set
            if paidout is not None:
                change = '-' + paidout
            elif paidin is not None:
                change = paidin
            else:
                raise RuntimeError("can't happen")

        yield Transaction(
            dt=cur_date,
            details=details,
            change_str=change,
            balance_str=balance,
        )
    assert len(cur_details) == 0


def as_pennies(x: str) -> int:
    if x[0] == '-':
        negative = True
        x = x[1:]
    else:
        negative = False

    gbp_s, pennies_s = x.split('.')
    assert len(pennies_s) == 2, x
    res = int(gbp_s) * 100 + int(pennies_s)
    if negative:
        res *= -1
    return res


def all_transactions(data: Path) -> Iterator[Transaction]:
    # todo add an option to skip balance checks?
    balance_pennies = 0
    for pdf in inputs(data):
        for t in extract_transactions(pdf):
            if t.change_str is not None:
                balance_pennies += as_pennies(t.change_str)
            if t.balance_str is not None:
                assert balance_pennies == as_pennies(t.balance_str), (balance_pennies, t.balance_str)
            yield t


if __name__ == '__main__':
    DATA = Path('TODO')
    for t in all_transactions(DATA):
        print(t)
