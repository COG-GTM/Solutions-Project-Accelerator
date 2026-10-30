"""Parse and rasterise SVG text that arrives with a project (imported archives,
project database rows, library symbols) without trusting it.

* XML is parsed with defusedxml: DTDs, entity declarations and external
  references are refused, so entity-expansion bombs never expand.
* The declared canvas size (width/height or viewBox) is bounded before
  CairoSVG sees the document, and the raster output is capped so a hostile
  SVG cannot make the renderer allocate a huge bitmap.
* CairoSVG is given a URL fetcher that only resolves ``data:`` URLs, so an SVG
  cannot make the workstation read local files or contact the network.
"""

import logging
import math
import os
import re
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

SVG_NAMESPACE = 'http://www.w3.org/2000/svg'

MAX_SVG_BYTES = 10 * 1024 * 1024
MAX_SVG_DIMENSION = 20000.0
MAX_RASTER_SIDE = 8192
MAX_RASTER_PIXELS = 8192 * 4096

COLOR_PLACEHOLDER = '{hex_color}'

# CSS absolute units in px at CairoSVG's default 96 dpi.
_UNIT_TO_PX = {
    '': 1.0,
    'px': 1.0,
    'pt': 96.0 / 72.0,
    'pc': 16.0,
    'mm': 96.0 / 25.4,
    'cm': 96.0 / 2.54,
    'in': 96.0,
}
_LENGTH_RE = re.compile(r'^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([a-zA-Z%]*)\s*$')
_NUMBER_RE = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')


class UnsafeSvgError(ValueError):
    """Raised when SVG content is malformed, too large, or otherwise refused."""


def _defused_parse(svg):
    size = len(svg.encode('utf-8', errors='replace')) if isinstance(svg, str) else len(svg)
    if size > MAX_SVG_BYTES:
        raise UnsafeSvgError(f"SVG is {size} bytes, limit is {MAX_SVG_BYTES}")
    ET.register_namespace('', SVG_NAMESPACE)
    try:
        return DefusedET.fromstring(svg, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (DefusedXmlException, ET.ParseError) as e:
        raise UnsafeSvgError(f"Refused SVG content: {e}") from e


def parse_svg(svg_string):
    """Parse SVG text with entity/DTD/external-reference protection and a bounded declared size."""
    if svg_string is None:
        raise UnsafeSvgError("No SVG content")
    root = _defused_parse(svg_string)
    declared_svg_size(root)
    return root


def read_svg_file(path):
    """Read an SVG file from a project folder, refusing oversized or unsafe content."""
    size = os.path.getsize(path)
    if size > MAX_SVG_BYTES:
        raise UnsafeSvgError(f"SVG file {path} is {size} bytes, limit is {MAX_SVG_BYTES}")
    with open(path, 'r', encoding='utf-8') as f:
        svg_string = f.read()
    parse_svg(svg_string)
    return svg_string


def _parse_length(value):
    """Return a length in px, None for percentages/missing, or raise for unsupported values."""
    if value is None:
        return None
    match = _LENGTH_RE.match(value)
    if not match:
        raise UnsafeSvgError(f"Unsupported SVG length {value!r}")
    number, unit = float(match.group(1)), match.group(2).lower()
    if unit == '%':
        return None
    if unit not in _UNIT_TO_PX:
        raise UnsafeSvgError(f"Unsupported SVG length unit {value!r}")
    return number * _UNIT_TO_PX[unit]


def _parse_viewbox(value):
    if not value:
        return None
    numbers = [float(n) for n in _NUMBER_RE.findall(value)]
    if len(numbers) != 4:
        return None
    return numbers


def _svg_size(root):
    """Return the (width, height) in px CairoSVG renders the root at, without size limits."""
    width = _parse_length(root.get('width'))
    height = _parse_length(root.get('height'))
    viewbox = _parse_viewbox(root.get('viewBox'))
    if viewbox is not None:
        if width is None:
            width = viewbox[2]
        if height is None:
            height = viewbox[3]
    if width is None or height is None:
        raise UnsafeSvgError("SVG declares no usable width/height or viewBox")
    if not (math.isfinite(width) and math.isfinite(height)) or width < 0 or height < 0:
        raise UnsafeSvgError(f"Invalid SVG size {width}x{height}")
    return width, height


def declared_svg_size(root):
    """Return the (width, height) in px the SVG declares, enforcing MAX_SVG_DIMENSION."""
    viewbox = _parse_viewbox(root.get('viewBox'))
    if viewbox is not None and not all(abs(v) <= MAX_SVG_DIMENSION for v in viewbox):
        raise UnsafeSvgError(f"SVG viewBox {root.get('viewBox')!r} exceeds {MAX_SVG_DIMENSION}")
    width, height = _svg_size(root)
    if width > MAX_SVG_DIMENSION or height > MAX_SVG_DIMENSION:
        raise UnsafeSvgError(f"SVG size {width}x{height} exceeds {MAX_SVG_DIMENSION}")
    return width, height


def apply_color_placeholder(svg_string, color):
    """Substitute the colour placeholder without str.format, so braces in SVG/CSS are left alone."""
    return svg_string.replace(COLOR_PLACEHOLDER, str(color))


def data_url_only_fetcher(url, resource_type):
    """CairoSVG url_fetcher that resolves embedded data: URLs and refuses everything else."""
    if not url.lower().startswith('data:'):
        raise UnsafeSvgError(f"Refused to load external SVG resource {url!r}")
    from cairosvg.url import fetch
    return fetch(url, resource_type)


def capped_output_size(width, height, scale=1.0):
    """Scale (width, height) by scale, shrinking proportionally to fit the raster caps."""
    out_width = max(width * scale, 1.0)
    out_height = max(height * scale, 1.0)
    factor = min(1.0,
                 MAX_RASTER_SIDE / out_width,
                 MAX_RASTER_SIDE / out_height,
                 (MAX_RASTER_PIXELS / (out_width * out_height)) ** 0.5)
    if factor < 1.0:
        logging.warning(f"Capping SVG raster from {out_width:.0f}x{out_height:.0f} "
                        f"to {out_width * factor:.0f}x{out_height * factor:.0f}")
    return out_width * factor, out_height * factor


def svg_to_png(svg, scale=1.0, write_to=None):
    """Rasterise SVG text/bytes to PNG with no external fetches, shrinking the output to the raster caps."""
    import cairosvg

    width, height = _svg_size(_defused_parse(svg))
    out_width, out_height = capped_output_size(width, height, scale)
    if isinstance(svg, str):
        svg = svg.encode('utf-8')
    return cairosvg.svg2png(bytestring=svg, write_to=write_to,
                            output_width=out_width, output_height=out_height,
                            unsafe=False, url_fetcher=data_url_only_fetcher)
