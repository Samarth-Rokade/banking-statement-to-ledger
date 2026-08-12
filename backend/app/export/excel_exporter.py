import io

from openpyxl import Workbook
from openpyxl.styles import Font

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


def export_excel(rows: list[ExportRow]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Vouchers"

    sheet.append(_HEADER)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for row_index, row in enumerate(rows, start=2):
        sheet.append(
            [
                row.txn_date,
                row.voucher_type,
                row.voucher_number,
                row.ledger_name,
                row.group_name,
                float(row.debit) if row.debit else None,
                float(row.credit) if row.credit else None,
                row.narration,
            ]
        )
        # openpyxl stores date/datetime values as their Excel serial number and
        # leaves the cell's display format as "General" unless told otherwise -
        # without this it renders as a raw number like "45550" instead of a date.
        sheet.cell(row=row_index, column=1).number_format = "DD-MMM-YYYY"

    for column_cells in sheet.columns:
        length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 60)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
