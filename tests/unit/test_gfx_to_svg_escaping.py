"""Unit tests for SVG escaping and safe rendering in bin/logic_gfx_to_svg.py.

Library symbol XML travels inside imported project archives, so attribute
values must not be able to inject markup into the generated SVG, and the
rasteriser must not fetch external resources.
"""

import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

import pytest

pytest.importorskip("svgpathtools")

from bin.logic_gfx_to_svg import data_only_url_fetcher, gfx_to_svg  # noqa: E402

SVG_NS = "{http://www.w3.org/2000/svg}"
INJECTION = '"/><image href="http://127.0.0.1:9/x"/><rect fill="'


def _symbol(*elements):
    return "<group>" + "".join(elements) + "</group>"


def _rect(back_color="#ff0000", fore_color="black", line_width="1"):
    return (
        f'<rectangle name="R1" left="0" top="0" width="40" height="20" '
        f'backStyle="solid" backColor={quoteattr(back_color)} '
        f'foreColor={quoteattr(fore_color)} lineWidth={quoteattr(line_width)}/>'
    )


def _text(caption, font_family="Arial"):
    return (
        f'<text name="T1" left="0" top="0" width="40" height="20" fontSize="8" '
        f'foreColor="black" fontFamily={quoteattr(font_family)} '
        f'caption={quoteattr(caption)}/>'
    )


def _render(xml):
    svg, viewbox, _, _ = gfx_to_svg(xml)
    assert viewbox is not None
    return ET.fromstring(svg)


class TestAttributeEscaping:
    @pytest.mark.parametrize("field", ["back_color", "fore_color", "line_width"])
    def test_rectangle_attribute_cannot_inject_elements(self, field):
        root = _render(_symbol(_rect(**{field: INJECTION})))

        assert root.findall(f".//{SVG_NS}image") == []
        rects = root.findall(f"{SVG_NS}rect")
        assert len(rects) == 1
        svg_attr = {"back_color": "fill", "fore_color": "stroke", "line_width": "stroke-width"}[field]
        assert rects[0].get(svg_attr) == INJECTION

    def test_text_caption_and_font_are_escaped(self):
        caption = '<image href="file:///etc/passwd"/> & more'
        root = _render(_symbol(_text(caption, font_family=INJECTION)))

        assert root.findall(f".//{SVG_NS}image") == []
        texts = root.findall(f"{SVG_NS}text")
        assert len(texts) == 1
        assert texts[0].text == caption
        assert texts[0].get("font-family") == INJECTION

    def test_benign_symbol_output_is_unchanged(self):
        svg, viewbox, _, _ = gfx_to_svg(_symbol(_rect(), _text("Pump 101")))

        assert viewbox == (0, 0, 40, 20)
        assert 'fill="#ff0000" stroke="black" stroke-width="1"' in svg
        assert ">Pump 101</text>" in svg


class TestDataOnlyUrlFetcher:
    @pytest.mark.parametrize("url", [
        "http://127.0.0.1:9/x",
        "https://mallory.example/ping",
        "file:///etc/passwd",
        "//mallory.example/ping",
        "C:/Windows/win.ini",
    ])
    def test_blocks_non_data_urls(self, url):
        with pytest.raises(ValueError):
            data_only_url_fetcher(url, "image/*")


class TestRenderSvgToPng:
    def test_uses_restricted_fetcher(self, monkeypatch):
        import sys
        import types

        from bin import logic_gfx_to_svg

        calls = []

        class FakePNGSurface:
            @classmethod
            def convert(cls, **kwargs):
                calls.append(kwargs)
                return b"png"

        fake_pkg = types.ModuleType("cairosvg")
        fake_surface = types.ModuleType("cairosvg.surface")
        fake_surface.PNGSurface = FakePNGSurface
        fake_pkg.surface = fake_surface
        monkeypatch.setitem(sys.modules, "cairosvg", fake_pkg)
        monkeypatch.setitem(sys.modules, "cairosvg.surface", fake_surface)

        assert logic_gfx_to_svg.render_svg_to_png("<svg/>", scale=2) == b"png"
        assert calls == [{
            "bytestring": b"<svg/>",
            "unsafe": False,
            "url_fetcher": logic_gfx_to_svg.data_only_url_fetcher,
            "scale": 2,
        }]

    def test_injected_image_is_never_fetched(self, monkeypatch):
        pytest.importorskip("cairosvg.surface")
        import cairosvg.url

        from bin import logic_gfx_to_svg

        offered = []
        real_fetcher = logic_gfx_to_svg.data_only_url_fetcher

        def spy(url, resource_type=None):
            offered.append(url)
            return real_fetcher(url, resource_type)

        def no_network(*args, **kwargs):
            raise AssertionError("cairosvg attempted to open a URL")

        monkeypatch.setattr(logic_gfx_to_svg, "data_only_url_fetcher", spy)
        monkeypatch.setattr(cairosvg.url, "urlopen", no_network, raising=False)

        svg, _, _, _ = gfx_to_svg(_symbol(_rect(back_color=INJECTION)))
        png = logic_gfx_to_svg.render_svg_to_png(svg)
        raw = ('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
               '<image href="http://127.0.0.1:9/x" width="10" height="10"/>'
               '<rect width="10" height="10" fill="red"/></svg>')
        raw_png = logic_gfx_to_svg.render_svg_to_png(raw)

        assert png.startswith(b"\x89PNG")
        assert raw_png.startswith(b"\x89PNG")
        assert all("127.0.0.1" in str(url) for url in offered)
