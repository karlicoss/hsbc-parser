#!/usr/bin/env python3
import pdfquery # type: ignore
from datetime import date, datetime
from typing import NamedTuple, List
from subprocess import check_output

class Transaction(NamedTuple):
    received: date
    date: date
    details: str
    amount: str


_DATE_FORMAT = "%d %b %y"

# TODO unhardcode
TABULA_PATH = '/L/zzz_syncthing/soft/tabula/tabula-1.0.2.jar'

def try_sanitize_amount(amnts):
    xxx = amnts.split()
    numberish = []
    for x in xxx:
        try:
            float(x)
        except ValueError:
            continue
        else:
            numberish.append(x)
    if len(numberish) == 1:
        return numberish[0]
    else:
        return amnts

# parses credit card statementc circa june 2018
def yield_credit_infos(fname: str):
    CMD = [
        'java',
        '-jar', TABULA_PATH,
        '--pages', 'all',
        '--silent',
        fname,
    ]
    res = check_output(CMD).decode('utf-8')

    def try_transaction(line):
        line = line.strip('"') # ugh, pdf sucks

        def try_parse_date(ds: str):
            try:
                return datetime.strptime(ds, _DATE_FORMAT)
            except:
                return None

        datelen = len("11 May 18")
        # TODO some stupid semicolon...
        rdates = line[:datelen]
        ddates = line[datelen + 1: datelen + 1 + datelen]
        ddates = ddates.replace(',', ' ') # sometimes there is random comma :shrug:
        rdate = try_parse_date(rdates)
        ddate = try_parse_date(ddates)
        if rdate is None and ddate is None:
            return

        rest = line[datelen + 1 + datelen:].split(',')
        amount = rest[-1]
        details = ' '.join(rest[:-1])

        # TODO sometimes it's necessary to sanitize amount...

        # if 'GRACEC' in details:
        #     import ipdb; ipdb.set_trace() 
        amount = try_sanitize_amount(amount)

        yield Transaction(
            received=rdate.date(),
            date=ddate.date(),
            details=details,
            amount=amount,
        )


    for line in res.splitlines():
        for t in try_transaction(line):
            yield t

# ugh. fuck it for now.
# def yield_debit_infos(fname: str):
#     pdf = pdfquery.PDFQuery(fname) # , parse_tree_cacher=FileCache("/tmp/")) # TODO more specific path?
#     pdf.load()

#     tdet = pdf.pq('LTTextBoxHorizontal:contains("see reverse")')[0]
#     children = list(tdet.getparent().iterchildren())[4:]
#     [date_col, _, _, _, _, comment_col] ..
#     pass

def get_credit_infos(fname: str) -> List[Transaction]:
    return list(yield_credit_infos(fname))

# def get_debit_infos(*args, **kwargs):
#     return list(yield_credit_infos)

def main():
    import sys
    pdf_path = sys.argv[1]

    infos = get_credit_infos(pdf_path)
    for info in infos:
        print(info)


if __name__ == '__main__':
    main()
