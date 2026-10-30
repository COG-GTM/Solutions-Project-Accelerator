"""SVG rendering must not follow external references (file://, http://, <use>, stylesheets)."""

import base64
import io
import urllib.request

import pytest

pytest.importorskip("cairosvg.surface")
from PIL import Image

from bin import logic_svg_render
from bin.logic_svg_render import open_svg_as_pillow_image, svg_bytes_to_png

RED = (255, 0, 0)


def _png(colour=RED, size=(4, 4)):
    buf = io.BytesIO()
    Image.new("RGB", size, colour).save(buf, "PNG")
    return buf.getvalue()


def _has_red(png_bytes):
    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return any(r > 200 and g < 60 and b < 60 for r, g, b in image.getdata())


def _svg(body, prolog=""):
    return (
        f'<?xml version="1.0"?>{prolog}'
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
        f' width="20" height="20"><rect width="20" height="20" fill="white"/>{body}</svg>'
    )


@pytest.fixture
def urlopen_calls(monkeypatch):
    calls = []

    def _record(url, *args, **kwargs):
        calls.append(getattr(url, "full_url", url))
        raise AssertionError(f"SVG render tried to open {calls[-1]}")

    monkeypatch.setattr(urllib.request, "urlopen", _record)
    import cairosvg.url

    monkeypatch.setattr(cairosvg.url, "urlopen", _record, raising=False)
    return calls


@pytest.fixture
def red_png_file(tmp_path):
    target = tmp_path / "secret.png"
    target.write_bytes(_png())
    return target


class TestExternalReferencesAreBlocked:
    def test_http_image_makes_no_request(self, urlopen_calls):
        png = svg_bytes_to_png(_svg('<image href="http://198.51.100.7/x.png" width="20" height="20"/>'))
        assert urlopen_calls == []
        assert png.startswith(b"\x89PNG")

    @pytest.mark.parametrize("attr", ["href", "xlink:href"])
    def test_file_url_image_is_not_read(self, urlopen_calls, red_png_file, attr):
        png = svg_bytes_to_png(_svg(f'<image {attr}="{red_png_file.as_uri()}" width="20" height="20"/>'))
        assert urlopen_calls == []
        assert not _has_red(png)

    def test_relative_image_next_to_the_svg_is_not_read(self, urlopen_calls, red_png_file):
        svg_path = red_png_file.parent / "graphic.svg"
        svg_path.write_text(_svg('<image href="secret.png" width="20" height="20"/>'))
        image = open_svg_as_pillow_image(str(svg_path)).convert("RGB")
        assert urlopen_calls == []
        assert (255, 0, 0) not in set(image.getdata())

    def test_use_of_external_svg_is_not_loaded(self, urlopen_calls, tmp_path):
        other = tmp_path / "other.svg"
        other.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><rect id="r" width="20" height="20" fill="red"/></svg>'
        )
        png = svg_bytes_to_png(_svg(f'<use xlink:href="{other.as_uri()}#r"/>'))
        assert urlopen_calls == []
        assert not _has_red(png)

    def test_external_stylesheet_is_not_loaded(self, urlopen_calls, tmp_path):
        css = tmp_path / "evil.css"
        css.write_text("rect.c { fill: red; }")
        png = svg_bytes_to_png(
            _svg(
                '<rect class="c" width="20" height="20" fill="white"/>',
                prolog=f'<?xml-stylesheet type="text/css" href="{css.as_uri()}"?>',
            )
        )
        assert urlopen_calls == []
        assert not _has_red(png)

    def test_fetcher_never_delegates_non_data_urls(self, urlopen_calls):
        for url in ("file:///etc/passwd", "http://169.254.169.254/latest", "https://example.com/a.css", "/etc/hosts"):
            assert logic_svg_render._offline_url_fetcher(url, "image/*") == logic_svg_render._EMPTY_SVG
        assert logic_svg_render._offline_url_fetcher("file:///x.css", "text/css") == b""
        assert urlopen_calls == []


class TestSelfContainedSvgsStillRender:
    def test_embedded_data_url_image_renders(self, urlopen_calls):
        data_url = "data:image/png;base64," + base64.b64encode(_png()).decode()
        png = svg_bytes_to_png(_svg(f'<image xlink:href="{data_url}" width="20" height="20"/>'))
        assert urlopen_calls == []
        assert _has_red(png)

    def test_open_pillow_image_renders_svg_file(self, tmp_path):
        from bin.logic_file_manager import Project_File_Manager

        svg_path = tmp_path / "graphic.SVG"
        svg_path.write_text(_svg('<rect x="5" y="5" width="10" height="10" fill="red"/>'))
        image = Project_File_Manager.open_pillow_image(str(svg_path))
        assert image.size == (20, 20)
        assert image.convert("RGB").getpixel((10, 10)) == RED

    def test_output_size_kwargs_are_passed_through(self):
        png = svg_bytes_to_png(_svg(""), output_width=40, output_height=30)
        assert Image.open(io.BytesIO(png)).size == (40, 30)


    def test_validator_rasterises_svg_offline(self, urlopen_calls, red_png_file):
        from bin.logic_validators import Validators

        svg_path = red_png_file.parent / "upload.svg"
        svg_path.write_text(_svg(f'<image href="{red_png_file.as_uri()}" width="20" height="20"/>'))
        assert Validators.check_svg_or_png(str(svg_path)) is True
        assert urlopen_calls == []

    def test_validator_rejects_non_svg_content(self, tmp_path):
        from bin.logic_validators import Validators

        bogus = tmp_path / "not.svg"
        bogus.write_text("this is not xml")
        assert Validators.check_svg_or_png(str(bogus)) is False

