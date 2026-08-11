from datetime import date
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel


class ParserError(Exception):
    """Raised when a statement file cannot be turned into transaction rows.

    The message is shown to the end user, so it must describe the problem in
    plain terms (e.g. "no transactions detected") rather than a stack trace.
    """


class TransactionRow(BaseModel):
    """Module 4 output shape - the only contract downstream modules rely on.

    No ledger/AI fields here on purpose: the parser's job is extraction only.
    """

    row_number: int
    txn_date: date
    description: str
    reference: str | None = None
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    balance: Decimal | None = None


class StatementParser(Protocol):
    def parse(self, content: bytes) -> list[TransactionRow]:
        """Parse raw file bytes into transaction rows, or raise ParserError."""
        ...
