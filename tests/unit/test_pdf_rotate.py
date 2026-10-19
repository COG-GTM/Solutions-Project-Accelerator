"""Unit tests for logic_pdf_render.rotate_pages, the pikepdf page rotation behind
the canvas rotate tools."""

import pikepdf
import pytest

from bin.logic_pdf_render import page_size, rotate_pages

SOURCE = 'demo/Simple Control Philosophy.pdf'


def rotations(path):
    with pikepdf.open(path) as pdf:
        return [page.rotation for page in pdf.pages]


@pytest.fixture
def pdf(tmp_path):
    out = tmp_path / 'rotate.pdf'
    with pikepdf.open(SOURCE) as src:
        del src.pages[3:]
        src.save(out)
    return str(out)


def test_rotates_only_the_requested_page(pdf):
    rotate_pages(pdf, 90, pnos=[1])
    assert rotations(pdf) == [0, 90, 0]


def test_rotates_every_page_by_default(pdf):
    rotate_pages(pdf, 90)
    assert rotations(pdf) == [90, 90, 90]


def test_rotation_is_relative_and_wraps_at_360(pdf):
    for _ in range(4):
        rotate_pages(pdf, 90, pnos=[0])
    assert rotations(pdf) == [0, 0, 0]


def test_repeated_rotation_leaves_a_readable_file(pdf):
    # Incremental saves used to need a reopen between calls or the file was damaged.
    portrait = page_size(pdf, 0)
    for _ in range(3):
        rotate_pages(pdf, 90, pnos=[0])
    assert page_size(pdf, 0) == (portrait[1], portrait[0])


def test_inherited_rotation_is_honoured(tmp_path):
    out = tmp_path / 'inherited.pdf'
    with pikepdf.open(SOURCE) as src:
        del src.pages[1:]
        src.save(out)
    # Move /Rotate off the page and onto the page-tree node, so it is only inherited.
    # pikepdf normalises that away on save, hence the byte patch.
    data = out.read_bytes()
    assert b'/Rotate 0' in data and b'/Type /Pages' in data
    data = data.replace(b'/Rotate 0', b' ' * len('/Rotate 0'), 1)
    out.write_bytes(data.replace(b'/Type /Pages', b'/Rotate 90 /Type /Pages', 1))

    rotate_pages(str(out), 90, pnos=[0])
    assert rotations(str(out)) == [180]


def test_rejects_rotations_that_are_not_a_quarter_turn(pdf):
    with pytest.raises(ValueError):
        rotate_pages(pdf, 45)
    assert rotations(pdf) == [0, 0, 0]
