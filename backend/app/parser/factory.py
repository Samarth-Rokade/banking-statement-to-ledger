from app.models.uploaded_file import FileType
from app.parser.base import StatementParser
from app.parser.csv_parser import CSVParser
from app.parser.excel_parser import ExcelParser
from app.parser.pdf_parser import PDFParser

_PARSERS: dict[FileType, type] = {
    FileType.CSV: CSVParser,
    FileType.XLSX: ExcelParser,
    FileType.PDF: PDFParser,
}


def get_parser(file_type: FileType) -> StatementParser:
    parser_cls = _PARSERS[file_type]
    return parser_cls()
