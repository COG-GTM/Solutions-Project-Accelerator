"""Rasterise SVGs with CairoSVG without letting the document reach outside itself.

Project SVGs can come from imported archives, so they are untrusted. By default
CairoSVG resolves ``<image>``, ``<use>``, ``xlink:href``, ``<?xml-stylesheet?>``
and CSS ``@import`` references through ``urllib``, which reads local files and
makes HTTP requests while rendering. Every render goes through
``_offline_url_fetcher`` instead: ``data:`` URLs embedded in the SVG are decoded
in-process and every other reference is replaced by an empty resource.
"""

import base64
import io
import logging
from urllib.parse import unquote_to_bytes

import cairosvg
from PIL import Image

logger = logging.getLogger(__name__)

_EMPTY_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'


def _decode_data_url(url):
    header, separator, payload = url[len('data:'):].partition(',')
    if not separator:
        raise ValueError('Malformed data URL in SVG')
    data = unquote_to_bytes(payload)
    if header.lower().endswith(';base64'):
        data = base64.b64decode(data)
    return data


def _offline_url_fetcher(url, resource_type=None):
    if url[:5].lower() == 'data:':
        return _decode_data_url(url)
    logger.warning('Blocked external SVG reference: %.200s', url)
    return b'' if resource_type == 'text/css' else _EMPTY_SVG


def svg_bytes_to_png(svg, **kwargs):
    """Render SVG markup (``str`` or ``bytes``) to PNG bytes with external references blocked."""
    if isinstance(svg, str):
        svg = svg.encode('utf-8')
    return cairosvg.svg2png(bytestring=svg, url_fetcher=_offline_url_fetcher, unsafe=False, **kwargs)


def svg_file_to_png(path, **kwargs):
    """Render the SVG file at ``path`` to PNG bytes with external references blocked."""
    with open(path, 'rb') as svg_file:
        return svg_bytes_to_png(svg_file.read(), **kwargs)


def open_svg_as_pillow_image(path, **kwargs):
    return Image.open(io.BytesIO(svg_file_to_png(path, **kwargs)))
