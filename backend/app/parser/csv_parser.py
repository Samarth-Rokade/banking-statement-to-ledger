import io

import pandas as pd

from app.parser.base import ParserError, TransactionRow
from app.parser.tabular_parser import dataframe_to_transactions


class CSVParser:
    def parse(self, content: bytes) -> list[TransactionRow]:
        try:
            df = pd.read_csv(io.BytesIO(content), dtype=str)
        except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
            raise ParserError("This CSV file could not be read; it may be corrupted.") from exc
        return dataframe_to_transactions(df)
