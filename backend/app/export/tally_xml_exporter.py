from xml.etree.ElementTree import Element, SubElement, tostring

from app.config.settings import get_settings
from app.export.service import ExportRow


def _add_ledger_entry(voucher_el: Element, ledger_name: str, is_debit: bool, amount) -> None:
    entry = SubElement(voucher_el, "ALLLEDGERENTRIES.LIST")
    SubElement(entry, "LEDGERNAME").text = ledger_name
    # Tally XML convention: a debit leg is ISDEEMEDPOSITIVE=Yes with a NEGATIVE
    # amount; a credit leg is ISDEEMEDPOSITIVE=No with a POSITIVE amount.
    SubElement(entry, "ISDEEMEDPOSITIVE").text = "Yes" if is_debit else "No"
    signed_amount = -amount if is_debit else amount
    SubElement(entry, "AMOUNT").text = f"{signed_amount:.2f}"


def _build_voucher(row: ExportRow, bank_ledger_name: str) -> Element:
    voucher = Element("VOUCHER", attrib={"VCHTYPE": row.voucher_type, "ACTION": "Create"})
    SubElement(voucher, "DATE").text = row.txn_date.strftime("%Y%m%d")
    SubElement(voucher, "VOUCHERTYPENAME").text = row.voucher_type
    SubElement(voucher, "VOUCHERNUMBER").text = row.voucher_number
    SubElement(voucher, "PARTYLEDGERNAME").text = row.ledger_name
    SubElement(voucher, "NARRATION").text = row.narration

    if row.debit > 0:
        # Money left the bank account: the bank ledger is credited, the resolved
        # ledger (an expense/creditor/self-transfer target) is debited.
        _add_ledger_entry(voucher, bank_ledger_name, is_debit=False, amount=row.debit)
        _add_ledger_entry(voucher, row.ledger_name, is_debit=True, amount=row.debit)
    else:
        # Money came into the bank account: the bank ledger is debited, the
        # resolved ledger (an income/debtor/self-transfer source) is credited.
        _add_ledger_entry(voucher, bank_ledger_name, is_debit=True, amount=row.credit)
        _add_ledger_entry(voucher, row.ledger_name, is_debit=False, amount=row.credit)

    return voucher


def export_tally_xml(rows: list[ExportRow]) -> bytes:
    settings = get_settings()

    envelope = Element("ENVELOPE")
    header = SubElement(envelope, "HEADER")
    SubElement(header, "TALLYREQUEST").text = "Import Data"

    body = SubElement(envelope, "BODY")
    import_data = SubElement(body, "IMPORTDATA")
    request_desc = SubElement(import_data, "REQUESTDESC")
    SubElement(request_desc, "REPORTNAME").text = "Vouchers"
    if settings.tally_company_name:
        static_vars = SubElement(request_desc, "STATICVARIABLES")
        SubElement(static_vars, "SVCURRENTCOMPANY").text = settings.tally_company_name

    request_data = SubElement(import_data, "REQUESTDATA")
    for row in rows:
        message = SubElement(request_data, "TALLYMESSAGE", attrib={"xmlns:UDF": "TallyUDF"})
        message.append(_build_voucher(row, settings.tally_bank_ledger_name))

    return tostring(envelope, encoding="utf-8", xml_declaration=True)
