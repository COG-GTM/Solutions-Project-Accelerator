"""Unit tests for bin/logic_pdf_tables.py, the pdfplumber table finder.

Reference values were verified byte-for-byte against a recorded baseline on the
same demo document: identical table count, bbox and extract() grid on every page.
"""

import pytest

from bin.logic_pdf_tables import find_tables

TEXT_DOCUMENT = 'demo/Simple Control Philosophy.pdf'


@pytest.fixture(scope='module')
def table():
    return find_tables(TEXT_DOCUMENT, 0)[0]


class TestFindTables:
    @pytest.mark.parametrize('pno, shapes', [
        (0, [(9, 9)]),
        (1, [(8, 9)]),
        (2, []),
        (3, [(42, 6)]),
        (4, [(6, 6)]),
    ])
    def test_shapes_match_the_baseline(self, pno, shapes):
        tables = find_tables(TEXT_DOCUMENT, pno)
        assert [(t.row_count, t.col_count) for t in tables] == shapes

    def test_bbox_matches_the_baseline(self, table):
        assert tuple(round(v, 2) for v in table.bbox) == (51.14, 487.04, 544.14, 631.04)

    def test_every_row_is_padded_to_the_column_count(self, table):
        assert len(table.rows) == table.row_count
        assert all(len(row.cells) == table.col_count for row in table.rows)

    def test_row_bbox_contains_its_cells(self, table):
        for row in table.rows:
            for cell in row.cells:
                if cell is None:
                    continue
                assert cell[0] >= row.bbox[0] - 0.01 and cell[2] <= row.bbox[2] + 0.01
                assert cell[1] >= row.bbox[1] - 0.01 and cell[3] <= row.bbox[3] + 0.01


class TestExtract:
    def test_grid_is_row_major_and_rectangular(self, table):
        grid = table.extract()
        assert len(grid) == table.row_count
        assert all(len(row) == table.col_count for row in grid)

    def test_first_row_is_the_column_headings(self, table):
        assert table.extract()[0] == ['Tag', 'Unit', 'Range', 'CtrlLo', 'CtrlHi',
                                      'LoLo', 'Lo', 'Hi', 'HiHi']

    def test_extract_returns_a_copy(self, table):
        grid = table.extract()
        grid[0][0] = 'mutated'
        assert table.extract()[0][0] == 'Tag'

    def test_table_outlives_the_document(self):
        # Callers stash tables in LLM context dicts and pass them to worker threads.
        table = find_tables(TEXT_DOCUMENT, 0)[0]
        assert table.extract() and table.to_markdown()


class TestHeader:
    def test_names_are_the_first_row(self, table):
        assert table.header.names == table.extract()[0]
        assert table.header.bbox == table.rows[0].bbox
        assert table.header.cells == table.rows[0].cells

    def test_header_is_never_external(self, table):
        # Markdown lines are numbered against row indices downstream, so promoting
        # text above the table would shift every row by one.
        assert table.header.external is False


class TestToMarkdown:
    def test_layout(self, table):
        lines = table.to_markdown().splitlines()
        assert lines[0] == '|Tag|Unit|Range|CtrlLo|CtrlHi|LoLo|Lo|Hi|HiHi|'
        assert lines[1] == '|' + '---|' * table.col_count
        assert lines[2].startswith('|TI-2007|deg C|')
        assert len([ln for ln in lines if ln.strip()]) == table.row_count + 1

    def test_separator_survives_the_caller_stripping_it(self, table):
        # gui_text_selector_tools strips '|---' then the '\n|\n' that is left over.
        stripped = table.to_markdown().replace('|---', '').replace('\n|\n', '\n')
        assert '---' not in stripped

    def test_unnamed_columns_get_a_placeholder(self):
        # The caller removes these again with a Col\d+ regex.
        assert 'Col5' in find_tables(TEXT_DOCUMENT, 4)[0].to_markdown().splitlines()[0]

    def test_newlines_in_a_cell_do_not_split_the_row(self):
        table = find_tables(TEXT_DOCUMENT, 4)[0]
        assert '<br>' in table.to_markdown()
        rows = [ln for ln in table.to_markdown().splitlines() if ln.strip()]
        assert len(rows) == table.row_count + 1

    def test_clean_escapes_markdown_syntax(self, table):
        assert '&#45;' in table.to_markdown(clean=True)

    def test_fill_empty_copies_left_then_down(self):
        table = find_tables(TEXT_DOCUMENT, 4)[0]
        grid = table.extract()
        merged = [(j, i) for j, row in enumerate(grid) for i, c in enumerate(row) if c is None]
        assert merged, 'this fixture is meant to contain merged cells'
        filled = table.to_markdown(fill_empty=True)
        assert '||' not in filled.splitlines()[0]
