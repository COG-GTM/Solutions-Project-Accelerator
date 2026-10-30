"""Imported HMI symbol SVGs must be validated/rendered offline and within size limits."""

import base64
import io
import time

import pytest
from PIL import Image

from bin import logic_svg_safety
from bin.logic_file_manager import Project_File_Manager
from bin.logic_svg_safety import (MAX_SVG_RENDER_SIDE, UnsafeSvgError, data_only_url_fetcher,
                                  inspect_svg, render_svg_to_png)
from bin.logic_validators import Validators

SVG_NS = 'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
PIXEL_PNG = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c63f8cfc0f01f0005000201a5f5d5a20000000049454e44ae426082"
)).decode()


def _write(tmp_path, body, name="symbol.svg"):
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


@pytest.fixture
def fetched_urls(monkeypatch):
    """Record every URL CairoSVG's default fetcher is asked for."""
    import cairosvg.url

    calls = []
    real_fetch = cairosvg.url.fetch

    def recording_fetch(url, resource_type):
        calls.append(url)
        return real_fetch(url, resource_type)

    monkeypatch.setattr(cairosvg.url, "fetch", recording_fetch)
    return calls


VALID_SVG = f'<svg {SVG_NS} width="64" height="32"><rect width="64" height="32" fill="red"/></svg>'


def test_valid_svg_is_accepted(tmp_path):
    assert Validators.check_svg_or_png(_write(tmp_path, VALID_SVG)) is True


def test_png_still_accepted(tmp_path):
    path = tmp_path / "symbol.png"
    path.write_bytes(base64.b64decode(PIXEL_PNG))
    assert Validators.check_svg_or_png(str(path)) is True


@pytest.mark.parametrize("body", [
    f'<svg {SVG_NS} width="10" height="10"><image href="http://127.0.0.1:9/x" width="10" height="10"/></svg>',
    f'<svg {SVG_NS} width="10" height="10"><image xlink:href="https://mallory.example/p.png"/></svg>',
    f'<svg {SVG_NS} width="10" height="10"><image xlink:href="file:///etc/passwd"/></svg>',
    f'<svg {SVG_NS} width="10" height="10"><use xlink:href="lib.svg#icon"/></svg>',
    f'<svg {SVG_NS} width="10" height="10"><rect style="fill:url(http://mallory.example/f)"/></svg>',
    f'<svg {SVG_NS} width="10" height="10"><rect fill="url(\'//mallory.example/f\')"/></svg>',
    f'<svg {SVG_NS} width="10" height="10"><style>@import url(x.css);</style></svg>',
    f'<svg {SVG_NS} width="10" height="10"><style>rect {{ fill: url(http://m.example/a) }}</style></svg>',
])
def test_external_references_are_rejected_without_fetching(tmp_path, fetched_urls, body):
    assert Validators.check_svg_or_png(_write(tmp_path, body)) is False
    assert fetched_urls == []


def test_data_uri_image_is_allowed(tmp_path):
    body = (f'<svg {SVG_NS} width="10" height="10">'
            f'<image xlink:href="data:image/png;base64,{PIXEL_PNG}" width="10" height="10"/></svg>')
    assert Validators.check_svg_or_png(_write(tmp_path, body)) is True


def test_url_fetcher_refuses_non_data_urls():
    with pytest.raises(UnsafeSvgError):
        data_only_url_fetcher("http://127.0.0.1:9/x", "image/*")
    with pytest.raises(UnsafeSvgError):
        data_only_url_fetcher("file:///etc/passwd", "image/*")


def test_huge_declared_size_is_rendered_capped_and_fast(tmp_path):
    body = (f'<svg {SVG_NS} width="100000" height="50000" viewBox="0 0 100000 50000">'
            '<rect width="100000" height="50000" fill="blue"/></svg>')
    path = _write(tmp_path, body)
    start = time.monotonic()
    assert Validators.check_svg_or_png(path) is True
    image = Project_File_Manager.open_pillow_image(path)
    assert time.monotonic() - start < 5
    assert image.size == (MAX_SVG_RENDER_SIDE, MAX_SVG_RENDER_SIDE // 2)


def test_huge_viewbox_without_size_is_capped(tmp_path):
    body = f'<svg {SVG_NS} viewBox="0 0 100000 100000"><circle cx="50000" cy="50000" r="40000"/></svg>'
    image = Image.open(io.BytesIO(render_svg_to_png(_write(tmp_path, body))))
    assert max(image.size) <= MAX_SVG_RENDER_SIDE


def test_small_svg_keeps_its_size(tmp_path):
    image = Project_File_Manager.open_pillow_image(_write(tmp_path, VALID_SVG))
    assert image.size == (64, 32)


def test_use_bomb_is_rejected(tmp_path):
    levels = ['<g id="l0"><rect width="1" height="1"/></g>']
    for i in range(1, 10):
        levels.append(f'<g id="l{i}">' + f'<use xlink:href="#l{i - 1}"/>' * 10 + '</g>')
    body = f'<svg {SVG_NS} width="10" height="10"><defs>{"".join(levels)}</defs><use xlink:href="#l9"/></svg>'
    path = _write(tmp_path, body)
    with pytest.raises(UnsafeSvgError, match="expands"):
        inspect_svg(path)
    assert Validators.check_svg_or_png(path) is False


def test_circular_use_is_rejected(tmp_path):
    body = f'<svg {SVG_NS} width="10" height="10"><g id="a"><use xlink:href="#a"/></g></svg>'
    assert Validators.check_svg_or_png(_write(tmp_path, body)) is False


def test_entity_expansion_is_rejected(tmp_path):
    body = ('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaaaaaaaa">'
            '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>'
            f'<svg {SVG_NS} width="10" height="10"><text>&b;</text></svg>')
    assert Validators.check_svg_or_png(_write(tmp_path, body)) is False


def test_external_entity_is_rejected(tmp_path, fetched_urls):
    body = ('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x SYSTEM "http://127.0.0.1:9/x">]>'
            f'<svg {SVG_NS} width="10" height="10"><text>&x;</text></svg>')
    assert Validators.check_svg_or_png(_write(tmp_path, body)) is False
    assert fetched_urls == []


@pytest.mark.parametrize("body", [
    '<html><body>not an svg</body></html>',
    'plain text',
    f'<svg {SVG_NS}><rect',
])
def test_non_svg_content_is_rejected(tmp_path, body):
    assert Validators.check_svg_or_png(_write(tmp_path, body)) is False


def test_oversized_file_is_rejected_before_parsing(tmp_path, monkeypatch):
    monkeypatch.setattr(logic_svg_safety, "MAX_SVG_FILE_BYTES", 100)
    padding = "<!--" + "x" * 200 + "-->"
    assert Validators.check_svg_or_png(_write(tmp_path, VALID_SVG + padding)) is False


def test_preview_render_rejects_external_reference(tmp_path, fetched_urls):
    body = f'<svg {SVG_NS} width="10" height="10"><image href="http://127.0.0.1:9/x"/></svg>'
    with pytest.raises(UnsafeSvgError):
        render_svg_to_png(_write(tmp_path, body))
    assert fetched_urls == []
