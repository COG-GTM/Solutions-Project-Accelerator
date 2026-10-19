"""Locate tables in a PDF page with pdfplumber (MIT).

The classes below expose only the part of the table API this app reads, and they
materialise everything up front: a table object outlives the document it came
from, because callers stash it in LLM context dicts and hand it to worker threads.
"""

import html

import pdfplumber


class TableRow:
    def __init__(self, cells, bbox):
        self.cells = cells
        self.bbox = bbox


class TableHeader:
    """The first table row. Text found *above* the table is never promoted into
    the header: the callers number markdown lines against row indices, so an
    external header would shift every row by one."""

    def __init__(self, bbox, cells, names):
        self.bbox = bbox
        self.cells = cells
        self.names = names
        self.external = False


class Table:
    def __init__(self, table):
        self.cells = [_bbox(c) for c in table.cells]
        self.rows = [TableRow([_bbox(c) for c in r.cells], _bbox(r.bbox)) for r in table.rows]
        self.bbox = _bbox(table.bbox)
        self.row_count = len(self.rows)
        self.col_count = max((len(r.cells) for r in self.rows), default=0)
        self.__grid = table.extract()
        first_row = self.rows[0] if self.rows else None
        self.header = TableHeader(
            first_row.bbox if first_row else None,
            first_row.cells if first_row else [],
            list(self.__grid[0]) if self.__grid else [],
        )

    def extract(self):
        """Cell text as a row-major grid; None for cells the finder did not find."""
        return [list(row) for row in self.__grid]

    def to_markdown(self, clean=False, fill_empty=True):
        """GitHub-flavoured markdown.

        :param clean: escape markdown syntax in the cell text.
        :param fill_empty: approximate row and column spans by copying the value
            to the left of, then above, every missing cell.
        """
        cells = self.extract()
        if fill_empty:
            for row in cells:
                for i in range(self.col_count - 1):
                    if row[i + 1] is None:
                        row[i + 1] = row[i]
            for i in range(self.col_count):
                for j in range(self.row_count - 1):
                    if cells[j + 1][i] is None:
                        cells[j + 1][i] = cells[j][i]

        names = [name or f'Col{i + 1}' for i, name in enumerate(self.header.names)]
        output = '|' + '|'.join(_md_cell(n, clean) for n in names) + '|\n'
        output += '|' + '|'.join('---' for _ in range(self.col_count)) + '|\n'
        for row in cells[1:]:  # row 0 is the header line above
            output += '|' + '|'.join(_md_cell(c, clean) for c in row) + '|\n'
        return output + '\n'


def _bbox(bbox):
    return tuple(bbox) if bbox is not None else None


def _md_cell(text, clean):
    text = text or ''
    if clean:
        text = html.escape(text).replace('-', '&#45;')
    return text.replace('\n', '<br>')  # a raw newline would split the row


def find_tables(pdf_path, pno, table_settings=None):
    """Return the tables on page `pno` of `pdf_path`, in pdfplumber's order."""
    with pdfplumber.open(pdf_path) as pdf:
        return [Table(t) for t in pdf.pages[pno].find_tables(table_settings or {})]
