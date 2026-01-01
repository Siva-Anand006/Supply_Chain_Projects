import sqlite3
from collections import defaultdict


def _fetch_actual(conn, source_type, source_id):
    rows = conn.execute(
        """
        SELECT l.acct, l.dr, l.cr
        FROM gl_header h
        JOIN gl_line l ON h.je_id = l.je_id
        WHERE h.source_type=? AND h.source_id=?
        """,
        (source_type, source_id),
    ).fetchall()

    return [{"acct": r["acct"], "dr": r["dr"], "cr": r["cr"]} for r in rows]


def _normalize(lines):
    agg = defaultdict(lambda: [0, 0])
    for l in lines:
        agg[l["acct"]][0] += l["dr"]
        agg[l["acct"]][1] += l["cr"]
    return {k: tuple(v) for k, v in agg.items()}


def validate_posting(conn, source_type, source_id, expected_lines):
    actual = _fetch_actual(conn, source_type, source_id)

    exp = _normalize(expected_lines)
    act = _normalize(actual)

    diffs = []
    for acct in set(exp) | set(act):
        if exp.get(acct, (0, 0)) != act.get(acct, (0, 0)):
            diffs.append(
                {
                    "account": acct,
                    "expected": exp.get(acct, (0, 0)),
                    "actual": act.get(acct, (0, 0)),
                }
            )

    return {
        "passed": len(diffs) == 0,
        "diffs": diffs,
        "expected": exp,
        "actual": act,
    }
