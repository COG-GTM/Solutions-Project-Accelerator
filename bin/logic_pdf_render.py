"""Rasterise PDF pages with pypdfium2 (Apache-2.0).

``thin_lines=True`` reproduces the OCR pre-pass that rewrites stroke-width
operators in the page content stream; PDFium cannot edit content streams, so
that step uses pikepdf (MPL-2.0).
"""

import io
import re
import threading

import pikepdf
import pypdfium2 as pdfium
from PIL import Image

# Any number followed by the PDF `w` (set line width) operator.
_LINE_WIDTH_OP = re.compile(rb'(\d+\.?\d*|\.\d+)\s+w')
_THIN = b'0.1 w'

# PDFium keeps process-global state and is not thread safe, while pypdfium2 is a
# ctypes binding that drops the GIL on every call. Nothing else serialises these
# calls, so without this lock the GUI thread rendering a page while a worker thread
# builds thumbnails corrupts PDFium and kills the app.
PDFIUM_LOCK = threading.RLock()

Image.MAX_IMAGE_PIXELS = None


def _thin_line_pdf(pdf_path, pno):
    """Return an in-memory single page PDF with page `pno`'s stroke widths forced thin."""
    with pikepdf.open(pdf_path) as pdf:
        page = pdf.pages[pno]
        page.contents_coalesce()
        page.obj.Contents.write(_LINE_WIDTH_OP.sub(_THIN, page.obj.Contents.read_bytes()))
        # Only the one page is saved; serialising the whole document here cost a full
        # copy of the PDF in memory for every page of an OCR scan.
        out = pikepdf.Pdf.new()
        out.pages.append(page)
        buf = io.BytesIO()
        out.save(buf)
        out.close()
    buf.seek(0)
    return buf


def page_size(pdf_path, pno):
    """Return (width, height) of page `pno` in PDF points."""
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_path)
        try:
            return doc[pno].get_size()
        finally:
            doc.close()


def page_count(pdf_path):
    """Return the number of pages in `pdf_path`."""
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_path)
        try:
            return len(doc)
        finally:
            doc.close()


def rotate_pages(pdf_path, degrees, pnos=None):
    """Rotate pages of `pdf_path` in place by `degrees`, relative to their current rotation.

    :param degrees: a multiple of 90; added to each page's existing /Rotate.
    :param pnos: 0-based page numbers to rotate, or None for every page.

    The caller must have released every other handle on the file first.
    """
    if degrees % 90:
        raise ValueError('PDF page rotation must be a multiple of 90 degrees')
    with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        targets = range(len(pdf.pages)) if pnos is None else pnos
        for pno in targets:
            page = pdf.pages[pno]
            # Building the page list pushes a /Rotate inherited from the page tree
            # down onto the page, so this reads the effective rotation.
            page.rotation = (page.rotation + degrees) % 360
        pdf.save(pdf_path)


def render_page(pdf_path, pno, zoom=1.0, clip=None, thin_lines=False, annots=True):
    """Render page `pno` to a PIL RGB image.

    :param pdf_path: path to a PDF, or the bytes of one.
    :param zoom: pixels per PDF point, applied uniformly to both axes.
    :param clip: optional (x0, y0, x1, y1) in PDF points with a top-left origin.
    :param thin_lines: rewrite stroke widths before rendering, for OCR.
    :param annots: draw the page's annotations.
    """
    source = pdf_path
    if thin_lines:
        source, pno = _thin_line_pdf(pdf_path, pno), 0
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(source)
        try:
            page = doc[pno]
            crop = (0, 0, 0, 0)
            if clip is not None:
                width, height = page.get_size()
                x0, y0, x1, y1 = clip
                # pypdfium2 wants insets from each edge, and its origin is bottom-left.
                crop = (
                    max(x0, 0),
                    max(height - y1, 0),
                    max(width - x1, 0),
                    max(y0, 0),
                )
            image = page.render(scale=zoom, crop=crop, draw_annots=annots).to_pil()
            page.close()
        finally:
            doc.close()
    # to_pil() already hands back RGB; converting again doubled peak memory on the
    # very large page rasters the scanner builds.
    return image if image.mode == 'RGB' else image.convert('RGB')


def render_page_png(pdf_path, pno, zoom=1.0, clip=None, thin_lines=False, annots=True):
    """Same as :func:`render_page` but returns PNG bytes."""
    buf = io.BytesIO()
    render_page(pdf_path, pno, zoom=zoom, clip=clip, thin_lines=thin_lines, annots=annots).save(buf, format='PNG')
    return buf.getvalue()
