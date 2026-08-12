import csv
import io

from app.export.service import ExportRow

_HEADER = [
    "Date",
    "Voucher Type",
    "Voucher Number",
    "Ledger",
    "Group",
    "Debit",
    "Credit",
    "Narration",
]


def export_csv(rows: list[ExportRow]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_HEADER)
    for row in rows:
        writer.writerow(
            [
                row.txn_date.isoformat(),
                row.voucher_type,
                row.voucher_number,
                row.ledger_name,
                row.group_name,
                f"{row.debit:.2f}" if row.debit else "",
                f"{row.credit:.2f}" if row.credit else "",
                row.narration,
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")  # BOM so Excel opens it as UTF-8, not Latin-1
