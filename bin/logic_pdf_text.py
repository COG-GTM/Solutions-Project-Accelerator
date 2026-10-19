"""Extract characters and search text with pypdfium2 (Apache-2.0).

Coordinates are UNROTATED mediabox space with a top-left origin, for both character
boxes and search hits, on rotated pages too, which is why callers carry a
``derotation_matrix`` next to every char.

Only ``c``, ``bbox`` and ``font`` are exposed; nothing in bin/ reads any other
per-character attribute. Char boxes come from ``FPDFText_GetLooseCharBox`` (the
font-metric box), not ``FPDFText_GetCharBox`` (the tighter ink box), because the
app's hit-testing is calibrated against the loose box.
"""

import ctypes
import math
import re

import pypdfium2 as pdfium
from pypdfium2 import raw as pr

from bin.logic_pdf_render import PDFIUM_LOCK

# PDFium emits these at line/run breaks with zero-area boxes; callers want neither.
_BREAKS = ('\r', '\n')

_WHITESPACE_RUN = re.compile(r'\s+')

# PDFium reports embedded subset fonts as "ABCDEF+Real-Name"; the tag is stripped.
_SUBSET_TAG = re.compile(r'^[A-Z]{6}\+')


class Rect:
    """The read-only rectangle the rest of the app expects back from a search."""

    __slots__ = ('x0', 'y0', 'x1', 'y1')

    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    def __iter__(self):
        return iter((self.x0, self.y0, self.x1, self.y1))

    def __getitem__(self, i):
        return (self.x0, self.y0, self.x1, self.y1)[i]

    def __len__(self):
        return 4

    def __eq__(self, other):
        return tuple(self) == tuple(other)

    @property
    def width(self):
        return self.x1 - self.x0

    @property
    def height(self):
        return self.y1 - self.y0

    def __repr__(self):
        return 'Rect({}, {}, {}, {})'.format(self.x0, self.y0, self.x1, self.y1)


def page_matrices(rot, width, height):
    """Return the page's derotation and rotation matrices as [a,b,c,d,e,f].

    Verified for rotations 0/90/180/270 at two page sizes.
    """
    derotation = {
        0: [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        90: [0.0, -1.0, 1.0, 0.0, 0.0, height],
        180: [-1.0, 0.0, 0.0, -1.0, width, height],
        270: [0.0, 1.0, -1.0, 0.0, width, 0.0],
    }[rot]
    rotation = {
        0: [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        90: [0.0, 1.0, -1.0, 0.0, height, 0.0],
        180: [-1.0, 0.0, 0.0, -1.0, width, height],
        270: [0.0, -1.0, 1.0, 0.0, 0.0, width],
    }[rot]
    return derotation, rotation


class PdfTextPage:
    """One page's characters, with the search helpers the app expects from a page."""

    def __init__(self, parent, pno):
        self.parent = parent
        self.number = pno
        page = parent._doc[pno]
        self._mediabox = page.get_mediabox()
        self._rotation = page.get_rotation() % 360
        textpage = page.get_textpage()
        self._chars, self._line_starts = self._extract(textpage, self._mediabox)
        textpage.close()
        page.close()
        self._text = ''.join(c['c'] for c in self._chars)
        self._norm, self._norm_to_char = self._normalise(self._text)
        self._blocks = None

    @staticmethod
    def _extract(textpage, mediabox):
        left, top = mediabox[0], mediabox[3]
        raw = textpage.raw
        count = pr.FPDFText_CountChars(raw)
        box = pr.FS_RECTF()
        matrix = pr.FS_MATRIX()
        name = ctypes.create_string_buffer(256)
        flags = ctypes.c_int()
        chars = []
        line_starts = []
        previous_font = ''
        broke = True
        for i in range(count):
            char = textpage.get_text_range(i, 1)
            if not char:
                continue
            if char in _BREAKS:
                broke = True
                continue
            if not pr.FPDFText_GetLooseCharBox(raw, i, ctypes.byref(box)):
                continue
            written = pr.FPDFText_GetFontInfo(raw, i, name, 256, ctypes.byref(flags))
            font = _SUBSET_TAG.sub('', name.raw[:written].decode('utf-8', 'replace').rstrip('\x00'))
            if font:
                # FPDFText_GetFontSize is the raw Tf operand; callers want the size
                # after the text matrix, which is Tf scaled by sqrt(|determinant|).
                size = abs(pr.FPDFText_GetFontSize(raw, i))
                if pr.FPDFText_GetMatrix(raw, i, ctypes.byref(matrix)):
                    size *= math.sqrt(abs(matrix.a * matrix.d - matrix.b * matrix.c))
                previous_font = '{} {}px'.format(font, int(size))
            if broke:
                line_starts.append(len(chars))
                broke = False
            chars.append({
                'c': char,
                'bbox': (box.left - left, top - box.top, box.right - left, top - box.bottom),
                # spaces often carry no font info, so they inherit their span's font
                'font': previous_font,
            })
        return chars, line_starts

    @staticmethod
    def _normalise(text):
        """Casefolded text with whitespace runs collapsed, plus a map back to char indexes."""
        out = []
        index = []
        previous_space = True
        for i, char in enumerate(text):
            if char.isspace():
                if previous_space:
                    continue
                out.append(' ')
                index.append(i)
                previous_space = True
            else:
                out.append(char.lower())
                index.append(i)
                previous_space = False
        return ''.join(out), index

    def chars(self, derotation_matrix=None, rotation_matrix=None):
        """Flat list of ``{'c', 'bbox', 'font'}`` dicts, in PDFium's reading order."""
        if derotation_matrix is None:
            return [dict(c) for c in self._chars]
        result = []
        for char in self._chars:
            copy = dict(char)
            copy['derotation_matrix'] = derotation_matrix
            copy['rotation_matrix'] = rotation_matrix
            result.append(copy)
        return result

    @property
    def text(self):
        return self._text

    def _lines(self):
        bounds = self._line_starts + [len(self._chars)]
        for start, end in zip(bounds, bounds[1:]):
            boxes = [self._chars[i]['bbox'] for i in range(start, end)
                     if not self._chars[i]['c'].isspace()]
            if not boxes:
                continue
            yield (start, end, (min(b[0] for b in boxes), min(b[1] for b in boxes),
                                max(b[2] for b in boxes), max(b[3] for b in boxes)))

    def blocks(self):
        """Text grouped into blocks, for callers that sort by y and join with a
        newline. PDFium's line runs give almost exactly one block per line
        (measured 1.00 to 1.04 blocks per line across the corpus).
        """
        if self._blocks is not None:
            return self._blocks
        groups = []
        for start, end, box in self._lines():
            groups.append({'bbox': box, 'chars': self._chars[start:end]})
        self._blocks = groups
        return groups

    @property
    def derotation_matrix(self):
        return page_matrices(self._rotation, self._width, self._height)[0]

    @property
    def rotation_matrix(self):
        return page_matrices(self._rotation, self._width, self._height)[1]

    @property
    def _width(self):
        return abs(self._mediabox[2] - self._mediabox[0])

    @property
    def _height(self):
        return abs(self._mediabox[3] - self._mediabox[1])

    def _group_rects(self, indexes):
        """Split a hit into one rect per line.

        Adjacency is measured as centre distance rather than vertical overlap, so
        that text rotated on the page (very common on P&IDs, where a tag runs
        bottom-to-top) stays a single rect instead of one rect per character.
        """
        groups = []
        current = []
        for i in indexes:
            char = self._chars[i]
            if char['c'].isspace():
                continue
            if current:
                previous = self._chars[current[-1]]['bbox']
                box = char['bbox']
                span = max(previous[2] - previous[0], previous[3] - previous[1],
                           box[2] - box[0], box[3] - box[1])
                gap = math.hypot((box[0] + box[2] - previous[0] - previous[2]) / 2.0,
                                 (box[1] + box[3] - previous[1] - previous[3]) / 2.0)
                if gap > 2.5 * max(span, 1e-6):
                    groups.append(current)
                    current = []
            current.append(i)
        if current:
            groups.append(current)
        out = []
        for group in groups:
            boxes = [self._chars[i]['bbox'] for i in group]
            out.append(Rect(min(b[0] for b in boxes), min(b[1] for b in boxes),
                            max(b[2] for b in boxes), max(b[3] for b in boxes)))
        return out

    def search_for(self, needle):
        """Case-insensitive search returning one Rect per line of each hit.

        Matching runs over this page's own characters, so a hit's rect is always
        consistent with the bboxes the rest of the app hit-tests against. Runs of
        whitespace match each other, which is what lets a query with a space match
        text broken across two lines.
        """
        if not needle:
            return []
        target = _WHITESPACE_RUN.sub(' ', needle).strip().lower()
        if not target:
            return []
        results = []
        start = self._norm.find(target)
        while start != -1:
            indexes = self._norm_to_char[start:start + len(target)]
            results.extend(self._group_rects(indexes))
            start = self._norm.find(target, start + 1)
        return results

    def get_textbox(self, rect):
        """Text whose character centres fall inside `rect`."""
        x0, y0, x1, y1 = tuple(rect)
        out = []
        for char in self._chars:
            box = char['bbox']
            cx = (box[0] + box[2]) / 2.0
            cy = (box[1] + box[3]) / 2.0
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                out.append(char['c'])
        return ''.join(out).strip()


class PdfTextDocument:
    """``doc[pno]`` handle exposing the page text API the app uses."""

    def __init__(self, path):
        self.name = path
        with PDFIUM_LOCK:
            self._doc = pdfium.PdfDocument(path)
        self._pages = {}

    def __getitem__(self, pno):
        page = self._pages.get(pno)
        if page is None:
            # PDFium is not thread safe and its state is process-global, so building a
            # page is serialised against every other PDFium call; everything after it
            # runs on the cached char list.
            with PDFIUM_LOCK:
                page = self._pages.get(pno)
                if page is None:
                    page = PdfTextPage(self, pno)
                    self._pages[pno] = page
        return page

    def __len__(self):
        return len(self._doc)

    def close(self):
        self._pages.clear()
        with PDFIUM_LOCK:
            self._doc.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


def open_text(path):
    """Open `path` for character extraction and searching."""
    return PdfTextDocument(path)
