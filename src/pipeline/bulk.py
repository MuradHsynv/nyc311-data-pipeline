"""Bulk upsert using COPY into a temp table, then INSERT ... ON CONFLICT."""

import csv
import io

NULL_MARK = "__NULL__"  # sentinel that lets COPY tell NULL apart from an empty string


def upsert_via_copy(conn, table, columns, rows, conflict_cols, update_cols=None):
    """Upsert rows (list of tuples in columns order) into table. Returns rows affected.

    conflict_cols: the unique key used for ON CONFLICT.
    update_cols:   columns overwritten on conflict (default: every non-key column).
    Rows must be unique by conflict_cols within one call.
    This function does NOT commit: the caller owns the transaction.
    """
    if not rows:
        return 0
    if update_cols is None:
        update_cols = [c for c in columns if c not in conflict_cols]
    col_list = ", ".join(columns)

    with conn.cursor() as cur:
        # Staging table with the same shape as the target, dropped automatically at commit
        # or rollback. IF NOT EXISTS plus TRUNCATE lets us call this many times per transaction.
        cur.execute(
            "CREATE TEMP TABLE IF NOT EXISTS _stage (LIKE "
            + table
            + " INCLUDING DEFAULTS) ON COMMIT DROP"
        )
        cur.execute("TRUNCATE _stage")

        # Serialize rows to CSV in memory and stream them in with COPY
        buf = io.StringIO()
        writer = csv.writer(buf)
        for row in rows:
            writer.writerow([NULL_MARK if value is None else value for value in row])
        buf.seek(0)
        cur.copy_expert(
            "COPY _stage ({0}) FROM STDIN WITH (FORMAT csv, NULL {1!r})".format(
                col_list, NULL_MARK
            ),
            buf,
        )

        # Merge staging into the real table
        if update_cols:
            action = "DO UPDATE SET " + ", ".join(
                "{0} = EXCLUDED.{0}".format(c) for c in update_cols
            )
        else:
            action = "DO NOTHING"
        cur.execute(
            "INSERT INTO {t} ({c}) SELECT {c} FROM _stage ON CONFLICT ({k}) {a}".format(
                t=table, c=col_list, k=", ".join(conflict_cols), a=action
            )
        )
        return cur.rowcount
