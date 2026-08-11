import io

import pandas as pd

from app.parser.base import ParserError, TransactionRow
from app.parser.tabular_parser import dataframe_to_transactions


class ExcelParser:
    def parse(self, content: bytes) -> list[TransactionRow]:
        try:
            df = pd.read_excel(io.BytesIO(content), dtype=str, engine="openpyxl")
        except (ValueError, KeyError) as exc:
            raise ParserError("This Excel file could not be read; it may be corrupted.") from exc
        return dataframe_to_transactions(df)
