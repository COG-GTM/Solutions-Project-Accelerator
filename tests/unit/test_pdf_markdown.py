"""Unit tests for bin/logic_pdf_markdown.py, the anymd markdown converter.

The two consumers in gui_text_selector_tools read the result as lines: one scans
for markdown list items (`__is_within_list`) and one for headings
(`extract_lists_with_headers`). The tests below pin that shape, not the bytes.
"""

import pytest

from bin.logic_pdf_markdown import find_anymd, page_to_markdown

TEXT_DOCUMENT = 'demo/Simple Control Philosophy.pdf'
DRAWING = 'demo/Demo P&ID.pdf'

pytestmark = [
    pytest.mark.allow_subprocess,
    pytest.mark.skipif(
        find_anymd() is None,
        reason='vendored anymd.exe absent; run build_scripts/setup_vendor_deps.ps1',
    ),
]


@pytest.fixture(scope='module')
def page_one():
    return page_to_markdown(TEXT_DOCUMENT, 0)


def test_returns_markdown_for_a_text_document(page_one):
    assert page_one.strip()
    assert 'INTERLOCKS' in page_one


def test_headings_are_atx_style(page_one):
    headings = [l for l in page_one.splitlines() if l.startswith('#')]
    assert headings
    assert all(l.split()[0].strip('#') == '' for l in headings)


def test_list_items_survive_as_markdown_bullets(page_one):
    bullets = [l for l in page_one.splitlines() if l.startswith('- ')]
    assert len(bullets) > 5


def test_tables_are_pipe_tables(page_one):
    assert any(l.startswith('|') for l in page_one.splitlines())


def test_page_marker_comments_are_stripped(page_one):
    assert '<!-- page' not in page_one


def test_pages_are_zero_based_and_distinct():
    assert page_to_markdown(TEXT_DOCUMENT, 0) != page_to_markdown(TEXT_DOCUMENT, 1)


def test_drawing_page_does_not_raise():
    assert isinstance(page_to_markdown(DRAWING, 0), str)


def test_missing_file_raises_runtime_error(tmp_path):
    with pytest.raises(RuntimeError):
        page_to_markdown(str(tmp_path / 'nope.pdf'), 0)
