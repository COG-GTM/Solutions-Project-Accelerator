"""Untrusted SVG from project archives must be parsed and rasterised with limits."""

import socket
import urllib.request

import pytest

from bin import logic_safe_svg
from bin.logic_safe_svg import UnsafeSvgError, parse_svg, read_svg_file, svg_to_png

SVG_NS = 'xmlns="http://www.w3.org/2000/svg"'
GOOD_SVG = (f'<svg {SVG_NS} width="40" height="20" viewBox="0 0 40 20">'
            '<rect x="1" y="1" width="38" height="18" stroke="#000" fill="none" stroke-width="1"/></svg>')
HUGE_SVG = (f'<svg {SVG_NS} width="100000" height="100000" viewBox="0 0 100000 100000">'
            '<rect width="100000" height="100000" fill="red"/></svg>')
HUGE_VIEWBOX_SVG = f'<svg {SVG_NS} viewBox="0 0 100000 100000"><rect width="10" height="10"/></svg>'
EXTERNAL_IMAGE_SVG = (f'<svg {SVG_NS} xmlns:xlink="http://www.w3.org/1999/xlink" width="10" height="10">'
                      '<image href="http://127.0.0.1:1/x" xlink:href="http://127.0.0.1:1/x" width="10" height="10"/></svg>')
LOCAL_FILE_IMAGE_SVG = (f'<svg {SVG_NS} width="10" height="10">'
                        '<image href="file:///etc/passwd" width="10" height="10"/></svg>')
ENTITY_BOMB_SVG = ('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaaaaaaaa">'
                   '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;"><!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>'
                   f'<svg {SVG_NS} width="10" height="10"><text>&c;</text></svg>')
EXTERNAL_ENTITY_SVG = ('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
                       f'<svg {SVG_NS} width="10" height="10"><text>&x;</text></svg>')


@pytest.fixture
def network_attempts(monkeypatch):
    attempts = []

    def _record(*args, **kwargs):
        attempts.append(args)
        raise RuntimeError("network disabled")

    monkeypatch.setattr(socket.socket, "connect", _record)
    monkeypatch.setattr(socket, "create_connection", _record)
    monkeypatch.setattr(urllib.request, "urlopen", _record)
    return attempts


def test_parse_accepts_normal_svg():
    root = parse_svg(GOOD_SVG)
    assert root.get('width') == '40'


@pytest.mark.parametrize("svg", [ENTITY_BOMB_SVG, EXTERNAL_ENTITY_SVG])
def test_parse_refuses_dtd_and_entities(svg):
    with pytest.raises(UnsafeSvgError):
        parse_svg(svg)


@pytest.mark.parametrize("svg", [HUGE_SVG, HUGE_VIEWBOX_SVG,
                                 f'<svg {SVG_NS} width="1e999" height="10"/>',
                                 f'<svg {SVG_NS} width="300in" height="10"/>',
                                 f'<svg {SVG_NS} width="10em" height="10"/>',
                                 f'<svg {SVG_NS} width="100%" height="100%"/>'])
def test_parse_refuses_oversized_or_unbounded_canvas(svg):
    with pytest.raises(UnsafeSvgError):
        parse_svg(svg)


def test_parse_refuses_oversized_document(monkeypatch):
    monkeypatch.setattr(logic_safe_svg, "MAX_SVG_BYTES", 100)
    with pytest.raises(UnsafeSvgError):
        parse_svg(GOOD_SVG + ' ' * 200)


def test_static_graphic_loader_refuses_huge_svg(tmp_path):
    path = tmp_path / "graphic.svg"
    path.write_text(HUGE_SVG, encoding="utf-8")
    with pytest.raises(UnsafeSvgError):
        read_svg_file(str(path))


def test_static_graphic_loader_refuses_entity_bomb(tmp_path):
    path = tmp_path / "graphic.svg"
    path.write_text(ENTITY_BOMB_SVG, encoding="utf-8")
    with pytest.raises(UnsafeSvgError):
        read_svg_file(str(path))


def test_static_graphic_loader_reads_normal_svg(tmp_path):
    path = tmp_path / "graphic.svg"
    path.write_text(GOOD_SVG, encoding="utf-8")
    assert read_svg_file(str(path)) == GOOD_SVG


def test_color_placeholder_leaves_css_braces_alone():
    svg = f'<svg {SVG_NS} width="1" height="1"><style>rect {{ fill: {{hex_color}}; }}</style></svg>'
    out = logic_safe_svg.apply_color_placeholder(svg, '#123456')
    assert 'rect { fill: #123456; }' in out


def test_raster_output_is_capped():
    width, height = logic_safe_svg.capped_output_size(100000, 100000)
    assert width <= logic_safe_svg.MAX_RASTER_SIDE
    assert width * height <= logic_safe_svg.MAX_RASTER_PIXELS + 1
    assert logic_safe_svg.capped_output_size(40, 20, 2.0) == (80, 40)


def test_fetcher_refuses_non_data_urls():
    for url in ("http://127.0.0.1:1/x", "https://example.com/a.png", "file:///etc/passwd", "/etc/passwd"):
        with pytest.raises(UnsafeSvgError):
            logic_safe_svg.data_url_only_fetcher(url, "image/*")


@pytest.fixture
def cairosvg():
    module = pytest.importorskip("cairosvg")
    if not hasattr(module, "svg2png"):
        pytest.skip("CairoSVG is not installed")
    return module


def _png_size(png):
    from io import BytesIO
    from PIL import Image
    return Image.open(BytesIO(png)).size


def test_render_normal_svg_at_scale(cairosvg):
    assert _png_size(svg_to_png(GOOD_SVG, scale=2.0)) == (80, 40)


def test_render_huge_svg_is_capped_not_allocated(cairosvg):
    width, height = _png_size(svg_to_png(HUGE_SVG))
    assert width <= logic_safe_svg.MAX_RASTER_SIDE and height <= logic_safe_svg.MAX_RASTER_SIDE
    assert width * height <= logic_safe_svg.MAX_RASTER_PIXELS


@pytest.mark.parametrize("svg", [EXTERNAL_IMAGE_SVG, LOCAL_FILE_IMAGE_SVG])
def test_render_never_fetches_external_resources(svg, cairosvg, network_attempts, monkeypatch):
    fetched = []
    real_fetch = cairosvg.url.fetch
    monkeypatch.setattr(cairosvg.url, "fetch", lambda url, rt: (fetched.append(url), real_fetch(url, rt))[1])
    try:
        svg_to_png(svg)
    except UnsafeSvgError:
        pass
    assert network_attempts == []
    assert fetched == []


def test_render_refuses_entity_bomb(cairosvg):
    with pytest.raises(UnsafeSvgError):
        svg_to_png(ENTITY_BOMB_SVG)
