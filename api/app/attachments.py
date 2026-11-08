"""Attachment conversion: a visitor's file becomes plain data for the model, or it is refused.

Responsibility: the type comes from the file's first bytes, never from its name or Content-Type. Only these get in
(pesquisa-seguranca-chat-portfolio.md, section 4):
- PNG, JPEG, WebP up to 5 MB: decoded and redrawn as a brand-new RGB PNG of its pixels, at most 1,600 px on the
  longer side, so EXIF, XMP, ICC and text chunks never pass. More than 25 million pixels is a bomb and is refused.
- PDF up to 10 MB and 20 pages: its text, page by page, up to 30,000 characters. Locked or text-less (scanned) PDFs
  are refused; metadata and embedded files are never read.
- XLSX up to 10 MB (20 MB unzipped, summed before opening; no macros): the values Excel stored, as CSV, visible
  sheets only, at most 200 rows by 30 columns. Nothing is calculated and links aren't followed.
- CSV up to 2 MB: UTF-8 without null bytes, kept as CSV within the same limits. Markup (SVG, HTML) is refused.
Anything else, or anything that fails to convert, raises Rejected with a reason: type, too_big, unreadable, no_text.
Text that hides inside a file (white text, a sheet cell) still comes through: it is data, and the prompt and the
output guard treat it as such.
Public API: convert, Converted, Rejected, IMAGE_SIDE.
Used by: app.attachment_sandbox (always inside the isolated child process, never in the API process).
Depends on: Pillow, pypdf, openpyxl (with defusedxml installed, which openpyxl uses for its XML).
Tests: tests/test_attachments.py.
"""

import csv
import io
import itertools
import warnings
import zipfile
from collections.abc import Iterable

from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfReader

from app.ports import Attachment, AttachmentRejected

MB = 1024 * 1024
IMAGE_MAX, PDF_MAX, XLSX_MAX, CSV_MAX = 5 * MB, 10 * MB, 10 * MB, 2 * MB
XLSX_UNZIPPED_MAX = 20 * MB
IMAGE_SIDE = 1600
MAX_PIXELS = 25_000_000
PDF_PAGES, TEXT_MAX = 20, 30_000
ROWS, COLS = 200, 30

Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # Pillow warns above this and raises above twice it; both are refused here


Converted, Rejected = Attachment, AttachmentRejected  # the names this module has always used


def convert(data: bytes) -> Converted:
    if data.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")) or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        return _image(data)
    if data.startswith(b"%PDF-"):
        return _pdf(data)
    if data.startswith(b"PK\x03\x04"):
        return _xlsx(data)
    return _csv(data)


def _limit(data: bytes, most: int) -> None:
    if len(data) > most:
        raise Rejected("too_big")


def _image(data: bytes) -> Converted:
    _limit(data, IMAGE_MAX)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(data))
            if img.format not in ("PNG", "JPEG", "WEBP"):
                raise Rejected("type")
            width, height = img.size
            rgb = img.convert("RGB")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise Rejected("too_big") from error
    except Rejected:
        raise
    except Exception as error:  # whatever the decoder chokes on is refused, never half-read
        raise Rejected("unreadable") from error
    rgb.thumbnail((IMAGE_SIDE, IMAGE_SIDE))
    clean = Image.frombytes("RGB", rgb.size, rgb.tobytes())  # pixels only: no info, EXIF or ICC carried over
    out = io.BytesIO()
    clean.save(out, "PNG")
    return Converted("image", f"image, {width}x{height}", png=out.getvalue())


def _pdf(data: bytes) -> Converted:
    _limit(data, PDF_MAX)
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise Rejected("unreadable")
        pages = len(reader.pages)
        if pages > PDF_PAGES:
            raise Rejected("too_big")
        text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    except Rejected:
        raise
    except Exception as error:
        raise Rejected("unreadable") from error
    if not text:
        raise Rejected("no_text")
    return Converted("pdf", f"pdf, {pages} page{'' if pages == 1 else 's'}", text=text[:TEXT_MAX])


def _xlsx(data: bytes) -> Converted:
    _limit(data, XLSX_MAX)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = set(z.namelist())
            unzipped = sum(info.file_size for info in z.infolist())
    except (zipfile.BadZipFile, ValueError) as error:
        raise Rejected("unreadable") from error
    if "xl/workbook.xml" not in names or "xl/vbaProject.bin" in names:
        raise Rejected("type")
    if unzipped > XLSX_UNZIPPED_MAX:
        raise Rejected("too_big")
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True, keep_links=False)
        rows = itertools.chain.from_iterable(
            ws.iter_rows(max_col=COLS, values_only=True) for ws in wb.worksheets if ws.sheet_state == "visible"
        )
        return _table(rows)
    except Exception as error:
        raise Rejected("unreadable") from error


def _csv(data: bytes) -> Converted:
    if not data:
        raise Rejected("type")
    _limit(data, CSV_MAX)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise Rejected("type") from error
    if "\x00" in text or text.lstrip().startswith("<"):
        raise Rejected("type")
    try:
        return _table(csv.reader(io.StringIO(text)))
    except csv.Error as error:
        raise Rejected("unreadable") from error


def _table(rows: Iterable) -> Converted:
    kept, more = [], False
    for row in rows:
        cells = ["" if value is None else str(value) for value in row][:COLS]
        while cells and cells[-1] == "":
            cells.pop()
        if not cells:
            continue
        if len(kept) == ROWS:
            more = True
            break
        kept.append(cells)
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(kept)
    summary = f"spreadsheet, first {ROWS} rows" if more else f"spreadsheet, {len(kept)} row{'' if len(kept) == 1 else 's'}"
    return Converted("spreadsheet", summary, text=out.getvalue())
