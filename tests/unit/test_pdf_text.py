"""Unit tests for bin/logic_pdf_text.py, the pypdfium2 text extraction layer.

Reference values were verified against a recorded baseline; see
/memories/repo/pdf_oxide_spike_result.md.
"""

import pikepdf
import pytest

from bin.logic_pdf_text import Rect, open_text

DRAWING = 'demo/Demo P&ID.pdf'
TEXT_DOCUMENT = 'demo/Simple Control Philosophy.pdf'


@pytest.fixture(scope='module')
def drawing_page():
    with open_text(DRAWING) as doc:
        yield doc[0]


@pytest.fixture(scope='module')
def text_page():
    with open_text(TEXT_DOCUMENT) as doc:
        yield doc[0]


def rotated_pdf(tmp_path, rotation):
    """Copy the first demo page with an explicit /Rotate."""
    out = tmp_path / 'rotated_{}.pdf'.format(rotation)
    with pikepdf.open(DRAWING) as pdf:
        del pdf.pages[1:]
        pdf.pages[0].Rotate = rotation
        pdf.save(out)
    return str(out)


class TestChars:
    def test_chars_have_the_contract_the_app_reads(self, drawing_page):
        chars = drawing_page.chars()
        assert chars
        assert all({'c', 'bbox', 'font'} <= set(c) for c in chars)
        assert all(len(c['bbox']) == 4 for c in chars)

    def test_line_break_characters_are_dropped(self, drawing_page):
        # PDFium emits \r\n at run breaks with zero-area boxes; callers want neither.
        assert not [c for c in drawing_page.chars() if c['c'] in ('\r', '\n')]

    def test_boxes_are_top_left_and_non_degenerate(self, drawing_page):
        for char in drawing_page.chars():
            x0, y0, x1, y1 = char['bbox']
            assert x1 >= x0 and y1 >= y0
            if not char['c'].isspace():
                assert x1 > x0 and y1 > y0

    def test_font_is_name_and_integer_size(self, text_page):
        fonts = {c['font'] for c in text_page.chars() if c['c'].strip()}
        assert fonts
        assert all(f.endswith('px') for f in fonts)
        assert all(f.split()[-1][:-2].isdigit() for f in fonts)

    def test_subset_prefix_is_stripped(self, drawing_page):
        # PDFium reports "ABCDEF+Arial"; the subset tag must be stripped.
        assert not [c for c in drawing_page.chars() if '+' in c['font']]

    def test_matrices_are_attached_when_requested(self, drawing_page):
        chars = drawing_page.chars(drawing_page.derotation_matrix,
                                   drawing_page.rotation_matrix)
        assert chars[0]['derotation_matrix'] == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        assert chars[0]['rotation_matrix'] == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

    def test_chars_are_copies_so_callers_cannot_corrupt_the_cache(self, drawing_page):
        drawing_page.chars()[0]['c'] = 'MUTATED'
        assert drawing_page.chars()[0]['c'] != 'MUTATED'


class TestMatrices:
    # Recorded baseline for page.derotation_matrix / rotation_matrix.
    @pytest.mark.parametrize('rotation, derotation, rotation_matrix', [
        (0, [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]),
        (90, [0.0, -1.0, 1.0, 0.0, 0.0, 841.89], [0.0, 1.0, -1.0, 0.0, 841.89, 0.0]),
        (180, [-1.0, 0.0, 0.0, -1.0, 1190.55, 841.89], [-1.0, 0.0, 0.0, -1.0, 1190.55, 841.89]),
        (270, [0.0, 1.0, -1.0, 0.0, 1190.55, 0.0], [0.0, -1.0, 1.0, 0.0, 0.0, 1190.55]),
    ])
    def test_matrices_match_the_baseline(self, tmp_path, rotation, derotation, rotation_matrix):
        with open_text(rotated_pdf(tmp_path, rotation)) as doc:
            page = doc[0]
            assert [round(v, 2) for v in page.derotation_matrix] == derotation
            assert [round(v, 2) for v in page.rotation_matrix] == rotation_matrix

    def test_char_boxes_stay_in_unrotated_space(self, tmp_path):
        """Chars are reported in unrotated mediabox space, so /Rotate must not move boxes.

        Only the visible characters are compared: PDFium's reading order changes with
        rotation, and it emits a couple of extra zero-area space characters.
        """
        boxes = {}
        for rotation in (0, 90, 180, 270):
            with open_text(rotated_pdf(tmp_path, rotation)) as doc:
                boxes[rotation] = sorted((c['c'], tuple(round(v, 3) for v in c['bbox']))
                                         for c in doc[0].chars() if not c['c'].isspace())
        assert boxes[0]
        assert boxes[90] == boxes[0]
        assert boxes[180] == boxes[0]
        assert boxes[270] == boxes[0]


class TestSearch:
    def test_finds_text_present_on_the_page(self, text_page):
        needle = ''.join(c['c'] for c in text_page.chars()[:6]).strip()
        assert needle
        assert text_page.search_for(needle)

    def test_is_case_insensitive(self, text_page):
        needle = ''.join(c['c'] for c in text_page.chars()[:6]).strip()
        assert len(text_page.search_for(needle.lower())) == \
               len(text_page.search_for(needle.upper()))

    def test_missing_text_returns_empty(self, text_page):
        assert text_page.search_for('zzzz-not-on-this-page-zzzz') == []

    def test_empty_needle_returns_empty(self, text_page):
        assert text_page.search_for('') == []
        assert text_page.search_for('   ') == []

    def test_rect_encloses_the_matched_characters(self, text_page):
        needle = ''.join(c['c'] for c in text_page.chars()[:6]).strip()
        rect = text_page.search_for(needle)[0]
        inside = [c for c in text_page.chars()
                  if rect.x0 - 0.1 <= (c['bbox'][0] + c['bbox'][2]) / 2 <= rect.x1 + 0.1
                  and rect.y0 - 0.1 <= (c['bbox'][1] + c['bbox'][3]) / 2 <= rect.y1 + 0.1]
        assert needle.replace(' ', '') in ''.join(c['c'] for c in inside).replace(' ', '')

    def test_whitespace_runs_match_each_other(self, text_page):
        """A query with a space must still match text broken across a line."""
        words = [w for w in text_page.text.split() if len(w) > 3]
        joined = ' '.join(words[:2])
        assert text_page.search_for(joined) == text_page.search_for(joined.replace(' ', '  '))


class TestBlocks:
    def test_blocks_cover_every_character(self, text_page):
        from_blocks = ''.join(c['c'] for b in text_page.blocks() for c in b['chars'])
        assert from_blocks == ''.join(c['c'] for c in text_page.chars())

    def test_block_bbox_contains_its_chars(self, text_page):
        for block in text_page.blocks():
            visible = [c['bbox'] for c in block['chars'] if not c['c'].isspace()]
            if not visible:
                continue
            assert block['bbox'][0] <= min(b[0] for b in visible) + 0.01
            assert block['bbox'][3] >= max(b[3] for b in visible) - 0.01


class TestGetTextbox:
    def test_returns_text_inside_the_rect(self, text_page):
        needle = ''.join(c['c'] for c in text_page.chars()[:6]).strip()
        rect = text_page.search_for(needle)[0]
        assert needle.replace(' ', '') in text_page.get_textbox(rect).replace(' ', '')

    def test_empty_rect_returns_empty_string(self, text_page):
        assert text_page.get_textbox(Rect(0, 0, 0, 0)) == ''


class TestDocument:
    def test_pages_are_cached(self):
        with open_text(DRAWING) as doc:
            assert doc[0] is doc[0]

    def test_len_matches_page_count(self):
        with open_text(DRAWING) as doc:
            assert len(doc) >= 1

    def test_name_exposes_the_path(self):
        with open_text(DRAWING) as doc:
            assert doc.name == DRAWING
            assert doc[0].parent.name == DRAWING
            assert doc[0].number == 0


class TestRect:
    def test_behaves_like_the_part_of_a_rect_callers_use(self):
        rect = Rect(1, 2, 4, 6)
        assert (rect.x0, rect.y0, rect.x1, rect.y1) == (1, 2, 4, 6)
        assert tuple(rect) == (1, 2, 4, 6)
        assert rect[0] == 1 and rect[3] == 6
        assert len(rect) == 4
        assert rect.width == 3 and rect.height == 4
