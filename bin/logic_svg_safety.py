"""Bounded, offline handling of untrusted SVG files (e.g. imported HMI symbols).

SVGs are parsed with defusedxml (no DTDs/entities), rejected if they reference
external resources or would expand into too many nodes, and rasterised by
CairoSVG with a ``data:``-only URL fetcher and a capped output size.
"""
import os
import re
from urllib.parse import urlparse

import cairosvg.surface
import cairosvg.url
from defusedxml import ElementTree as DefusedET

MAX_SVG_FILE_BYTES = 5 * 1024 * 1024
MAX_SVG_EXPANDED_NODES = 20000
MAX_SVG_RENDER_SIDE = 2048
VALIDATION_RENDER_SIDE = 256

_UNIT_TO_PX = {'': 1.0, 'px': 1.0, 'pt': 96 / 72, 'pc': 16.0, 'mm': 96 / 25.4,
               'cm': 96 / 2.54, 'in': 96.0, 'em': 16.0, 'ex': 8.0}
_LENGTH_RE = re.compile(r'^\s*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*([a-zA-Z]*)\s*$')
_CSS_URL_RE = re.compile(r'url\(\s*([\'"]?)(.*?)\1\s*\)', re.IGNORECASE | re.DOTALL)
_CSS_IMPORT_RE = re.compile(r'@import', re.IGNORECASE)
_HREF_ATTRS = ('href', '{http://www.w3.org/1999/xlink}href')


class UnsafeSvgError(ValueError):
    """Raised when an SVG is malformed, too large or references external resources."""


def _local_name(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _is_local_reference(value):
    value = value.strip()
    return value == '' or value.startswith('#') or value.lower().startswith('data:')


def _url_string(url):
    return url.geturl() if hasattr(url, 'geturl') else str(url)


def data_only_url_fetcher(url, resource_type):
    """CairoSVG url_fetcher that resolves inline ``data:`` URLs and refuses everything else."""
    url = _url_string(url)
    if urlparse(url).scheme.lower() != 'data':
        raise UnsafeSvgError('External SVG resource blocked: {}'.format(url[:100]))
    return cairosvg.url.fetch(url, resource_type)


def _read_svg_bytes(path):
    if os.path.getsize(path) > MAX_SVG_FILE_BYTES:
        raise UnsafeSvgError('SVG file is larger than {} bytes'.format(MAX_SVG_FILE_BYTES))
    with open(path, 'rb') as file:
        return file.read(MAX_SVG_FILE_BYTES + 1)


def _check_external_references(root):
    for element in root.iter():
        for attr in _HREF_ATTRS:
            value = element.get(attr)
            if value is not None and not _is_local_reference(value):
                raise UnsafeSvgError('SVG references an external resource: {}'.format(value[:100]))
        css = [element.get('style') or '']
        if _local_name(element.tag) == 'style':
            css.append(element.text or '')
        css.extend(value for name, value in element.attrib.items() if 'url(' in value.lower())
        for text in css:
            if _CSS_IMPORT_RE.search(text):
                raise UnsafeSvgError('SVG stylesheet uses @import')
            for _, target in _CSS_URL_RE.findall(text):
                if not _is_local_reference(target):
                    raise UnsafeSvgError('SVG references an external resource: {}'.format(target[:100]))


def _check_expanded_size(root):
    """Bound the node count after <use> expansion, which catches 'use bombs' and cycles."""
    by_id = {element.get('id'): element for element in root.iter() if element.get('id')}
    memo = {}
    in_progress = set()

    def weight(element):
        key = id(element)
        if key in memo:
            return memo[key]
        if key in in_progress:
            raise UnsafeSvgError('SVG contains a circular <use> reference')
        in_progress.add(key)
        total = 1
        if _local_name(element.tag) == 'use':
            href = next((element.get(a) for a in _HREF_ATTRS if element.get(a)), '')
            target = by_id.get(href.strip()[1:]) if href.strip().startswith('#') else None
            if target is not None:
                total += weight(target)
        for child in element:
            total += weight(child)
            if total > MAX_SVG_EXPANDED_NODES:
                break
        in_progress.discard(key)
        if total > MAX_SVG_EXPANDED_NODES:
            raise UnsafeSvgError('SVG expands to more than {} nodes'.format(MAX_SVG_EXPANDED_NODES))
        memo[key] = total
        return total

    weight(root)


def inspect_svg(path):
    """Parse and check an untrusted SVG without rendering it.

    :returns: (svg bytes, root element)
    :raises UnsafeSvgError: if the file is not a safe, well-formed SVG.
    """
    data = _read_svg_bytes(path)
    try:
        root = DefusedET.fromstring(data)
    except Exception as error:
        raise UnsafeSvgError('Not a well-formed SVG document: {}'.format(error)) from error
    if _local_name(root.tag) != 'svg':
        raise UnsafeSvgError('Root element is not <svg>')
    _check_external_references(root)
    _check_expanded_size(root)
    return data, root


def _length_px(value):
    match = _LENGTH_RE.match(value or '')
    if not match or match.group(2).lower() not in _UNIT_TO_PX:
        return None
    return float(match.group(1)) * _UNIT_TO_PX[match.group(2).lower()]


def _intrinsic_size(root):
    width, height = _length_px(root.get('width')), _length_px(root.get('height'))
    view_box = (root.get('viewBox') or '').replace(',', ' ').split()
    if len(view_box) == 4:
        try:
            vb_width, vb_height = abs(float(view_box[2])), abs(float(view_box[3]))
        except ValueError:
            vb_width = vb_height = 0
        if vb_width and vb_height:
            if width and not height:
                height = width * vb_height / vb_width
            elif height and not width:
                width = height * vb_width / vb_height
            elif not width and not height:
                width, height = vb_width, vb_height
    if not width or not height:
        return None
    return width, height


def _bounded_output_size(root, max_side):
    size = _intrinsic_size(root)
    if size is None:
        return max_side, max_side
    width, height = size
    scale = min(1.0, max_side / max(width, height))
    return max(1, round(width * scale)), max(1, round(height * scale))


def render_svg_to_png(path, max_side=MAX_SVG_RENDER_SIDE):
    """Rasterise an untrusted SVG offline with the longest side capped at ``max_side`` pixels."""
    data, root = inspect_svg(path)
    output_width, output_height = _bounded_output_size(root, max_side)
    # svg2png() has no url_fetcher argument; convert() forwards it to the parser Tree.
    return cairosvg.surface.PNGSurface.convert(
        bytestring=data, url_fetcher=data_only_url_fetcher, unsafe=False,
        output_width=output_width, output_height=output_height)


def is_safe_svg(path):
    """True if ``path`` is a well-formed, self-contained SVG that renders within the limits."""
    try:
        render_svg_to_png(path, max_side=VALIDATION_RENDER_SIDE)
    except Exception:
        return False
    return True
