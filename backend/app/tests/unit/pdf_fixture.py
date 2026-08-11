def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_simple_pdf(lines: list[str]) -> bytes:
    """Build a minimal single-page PDF whose content stream draws each string as a
    left-aligned text line, top to bottom, with no table borders.
    """
    content_lines = ["BT", "/F1 10 Tf", "50 750 Td"]
    for i, line in enumerate(lines):
        if i > 0:
            content_lines.append("0 -14 Td")
        content_lines.append(f"({_escape(line)}) Tj")
    content_lines.append("ET")
    return _wrap_pdf(content_lines)


def build_table_pdf(
    rows: list[list[str]],
    col_widths: list[float],
    row_height: float = 30,
    start_x: float = 50,
    start_y: float = 780,
) -> bytes:
    """Build a minimal single-page PDF with an actual ruled table: each cell gets a
    stroked border rectangle, so pdfplumber's default (line-based) table detector
    recognizes it the same way it does a real bordered bank-statement table. Cell
    text may contain "\\n" to simulate a narration wrapped across physical lines
    within one logical table row.
    """
    content_lines: list[str] = []
    y = start_y

    for row in rows:
        x = start_x
        for col_index, cell_text in enumerate(row):
            width = col_widths[col_index]
            content_lines.append(f"{x} {y - row_height} {width} {row_height} re S")

            content_lines.append("BT")
            content_lines.append("/F1 8 Tf")
            content_lines.append(f"{x + 2} {y - 12} Td")
            cell_lines = cell_text.split("\n")
            for i, line in enumerate(cell_lines):
                if i > 0:
                    content_lines.append("0 -10 Td")
                content_lines.append(f"({_escape(line)}) Tj")
            content_lines.append("ET")
            x += width
        y -= row_height

    return _wrap_pdf(content_lines)


def _wrap_pdf(content_lines: list[str]) -> bytes:
    stream_content = "\n".join(content_lines).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream_content)).encode() + b" >>\nstream\n"
        + stream_content
        + b"\nendstream",
    ]

    buffer = bytearray()
    buffer.extend(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer.extend(f"{index} 0 obj\n".encode())
        buffer.extend(body)
        buffer.extend(b"\nendobj\n")

    xref_offset = len(buffer)
    num_objects = len(objects) + 1
    buffer.extend(f"xref\n0 {num_objects}\n".encode())
    buffer.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.extend(f"{offset:010d} 00000 n \n".encode())
    buffer.extend(
        f"trailer\n<< /Size {num_objects} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
    )
    return bytes(buffer)
