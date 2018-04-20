#!/usr/bin/env python3
import pdfquery # type: ignore
from pdfquery.cache import FileCache
from datetime import date, datetime
from typing import NamedTuple, List

class Transaction(NamedTuple):
    received: date
    date: date
    details: str
    amount: str


_DATE_FORMAT = "%d %b %y"

# parses credit card statementc circa april 2018
def yield_credit_infos(fname: str):
    pdf = pdfquery.PDFQuery(fname) # , parse_tree_cacher=FileCache("/tmp/")) # TODO more specific path?
    print(fname)
    # TODO wtf?? returns frong file..
    pdf.load()

    tdet = pdf.pq('LTTextBoxHorizontal:contains("Transaction Details")')[0]

    [_, received_date_col, transation_date_col, details_col, _, _, _, _, amount_col] = list(tdet.itersiblings())[:9]

    received_dates = list(received_date_col.itertext())
    transation_dates = list(transation_date_col.itertext())
    details = list(details_col.itertext())
    amounts = list(amount_col.itertext())

    infos = list(zip(received_dates, transation_dates, details, amounts))

    for info in infos:
        if all(s == '' for s in info):
            # sometimes there is an empty line.. weird
            # TODO stderr?
            continue
        [recvs, trans, det, amount] = info
        recv_date = datetime.strptime(recvs.strip(), _DATE_FORMAT).date()
        trans_date = datetime.strptime(trans.strip(), _DATE_FORMAT).date()
        yield Transaction(
            received=recv_date,
            date=trans_date,
            details=det.strip(),
            amount=amount.strip()
        )

def get_gredit_infos(fname: str) -> List[Transaction]:
    return list(yield_credit_infos(fname))

def main():
    import sys
    pdf_path = sys.argv[1]

    infos = get_credit_infos(pdf_path)
    for info in infos:
        print(info)


if __name__ == '__main__':
    main()
