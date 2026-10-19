"""Unit tests for the pypdf/pikepdf annotation, link and page-composition helpers:
bin/logic_pdf_export, bin/logic_export_approved_annotations
and create_pdf_from_cropped_pages.

Every expected rect below is a recorded baseline, captured from the same file at
the same /Rotate and compared byte for byte.
"""

import shutil

import pikepdf
import pytest
from pypdf import PdfReader

from bin.logic_border_detection_cropper import create_pdf_from_cropped_pages
from bin.logic_export_approved_annotations import ApprovedAnnotationExporter, _rgb_to_hex
from bin.logic_pdf_export import pdf_with_data_exporter

DRAWING = 'demo/Demo P&ID.pdf'
TEXT_DOC = 'demo/Simple Control Philosophy.pdf'

LINK_RECT = (0.1, 0.2, 0.35, 0.3)
ANNOT_POINT = [0.4, 0.6]

# (rotation, link /Rect, text annotation /Rect) baselines.
BASELINE_RECTS = [
    (0, [119.06, 589.32, 416.69, 673.51], [477.22, 317.76, 495.22, 335.76]),
    (90, [238.11, 84.19, 357.17, 294.66], [715.33, 317.76, 733.33, 335.76]),
    (180, [773.86, 168.38, 1071.5, 252.57], [715.33, 486.13, 733.33, 504.13]),
    (270, [833.39, 547.23, 952.44, 757.7], [477.22, 486.13, 495.22, 504.13]),
]


def rotated_copy(source, degrees, path):
    with pikepdf.open(source) as pdf:
        for page in pdf.pages:
            page.rotate(degrees, False)
        pdf.save(path)
    return str(path)


def annotations(path, subtype):
    page = PdfReader(path).pages[0]
    return [ref.get_object() for ref in page.get('/Annots', [])
            if ref.get_object()['/Subtype'] == subtype]


class TestPdfWithDataExporter:
    @pytest.fixture
    def exported(self, tmp_path, request):
        degrees = getattr(request, 'param', 0)
        source = rotated_copy(DRAWING, degrees, tmp_path / 'src.pdf')
        exporter = pdf_with_data_exporter(source)
        exporter.create_page_link(0, LINK_RECT, 1)
        exporter.create_annotation(0, ANNOT_POINT, 'TAG-001', 'a description')
        out = tmp_path / 'out.pdf'
        exporter.export_pdf(str(out))
        return str(out)

    def test_page_count_matches_the_source(self, tmp_path):
        exporter = pdf_with_data_exporter(DRAWING)
        with pikepdf.open(DRAWING) as pdf:
            assert exporter.get_number_of_pages() == len(pdf.pages)

    @pytest.mark.parametrize('exported,expected',
                             [(r, link) for r, link, _ in BASELINE_RECTS],
                             indirect=['exported'])
    def test_link_rect_matches_the_baseline(self, exported, expected):
        link, = annotations(exported, '/Link')
        assert [round(float(v), 2) for v in link['/Rect']] == expected

    @pytest.mark.parametrize('exported,expected',
                             [(r, annot) for r, _, annot in BASELINE_RECTS],
                             indirect=['exported'])
    def test_text_annot_rect_matches_the_baseline(self, exported, expected):
        annot, = annotations(exported, '/Text')
        assert [round(float(v), 2) for v in annot['/Rect']] == expected

    def test_link_targets_the_requested_page(self, exported):
        link, = annotations(exported, '/Link')
        reader = PdfReader(exported)
        # a /Dest in this document must name the page object, not a page number
        assert link['/Dest'][0].idnum == reader.pages[1].indirect_reference.idnum
        assert link['/Dest'][1] == '/XYZ'

    def test_text_annot_carries_the_name_and_the_tag_icon(self, exported):
        annot, = annotations(exported, '/Text')
        assert annot['/Contents'] == 'TAG-001'
        assert annot['/Name'] == '/Tag'

    def test_save_pdf_writes_back_over_the_source(self, tmp_path):
        source = tmp_path / 'inplace.pdf'
        shutil.copy(DRAWING, source)
        exporter = pdf_with_data_exporter(str(source))
        exporter.create_annotation(0, ANNOT_POINT, 'TAG-001', '')
        exporter.save_pdf()
        assert len(annotations(str(source), '/Text')) == 1


class TestApprovedAnnotationHighlights:
    RECT = (72.0, 100.0, 220.0, 112.0)  # unrotated top-left space, as chars report

    @pytest.fixture
    def exporter(self, tmp_path):
        source = tmp_path / 'text.pdf'
        shutil.copy(TEXT_DOC, source)
        exporter = ApprovedAnnotationExporter(str(source), db=None)
        yield exporter
        exporter.close()

    def test_rgb_to_hex_uses_the_approved_green(self):
        assert _rgb_to_hex(ApprovedAnnotationExporter.DEFAULT_COLOR) == '8dcc8f'

    @pytest.mark.parametrize('degrees', [0, 90, 180, 270])
    def test_quad_points_match_the_baseline_and_ignore_page_rotation(self, tmp_path, degrees):
        source = rotated_copy(TEXT_DOC, degrees, tmp_path / 'rot.pdf')
        exporter = ApprovedAnnotationExporter(source, db=None)
        try:
            page = exporter.doc.pages[0]
            exporter.doc.add_annotation(
                page_number=0,
                annotation=exporter._build_annotation(
                    exporter._to_pdf_rect(page, self.RECT), 'Approved: X'))
            out = tmp_path / 'hl{}.pdf'.format(degrees)
            exporter.save(str(out))
        finally:
            exporter.close()

        highlight, = annotations(str(out), '/Highlight')
        assert [round(float(v), 2) for v in highlight['/QuadPoints']] == [
            72.0, 741.89, 220.0, 741.89, 72.0, 729.89, 220.0, 729.89]

    def test_colour_opacity_and_contents_are_set(self, exporter, tmp_path):
        page = exporter.doc.pages[0]
        exporter.doc.add_annotation(
            page_number=0,
            annotation=exporter._build_annotation(
                exporter._to_pdf_rect(page, self.RECT), 'Approved: TAG-1'))
        out = tmp_path / 'coloured.pdf'
        exporter.save(str(out))

        highlight, = annotations(str(out), '/Highlight')
        assert [round(float(v), 3) for v in highlight['/C']] == [0.553, 0.8, 0.561]
        assert round(float(highlight['/CA']), 2) == 0.3
        assert highlight['/Contents'] == 'Approved: TAG-1'

    def test_build_highlight_rects_groups_characters_into_lines(self, exporter):
        chars = [{'bbox': (10, 20, 14, 30)}, {'bbox': (14, 20.2, 19, 30)},
                 {'bbox': (10, 40, 14, 50)}]
        assert sorted(exporter._build_highlight_rects(chars)) == [
            (10, 20, 19, 30), (10, 40, 14, 50)]

    def test_no_characters_means_no_rects(self, exporter):
        assert exporter._build_highlight_rects([]) == []

    def test_page_count_matches_the_source(self, exporter):
        with pikepdf.open(TEXT_DOC) as pdf:
            assert exporter.get_number_of_pages() == len(pdf.pages)


class TestCreatePdfFromCroppedPages:
    @pytest.fixture
    def source(self, tmp_path):
        work = tmp_path / 'crop_in.pdf'
        with pikepdf.open(DRAWING) as pdf:
            del pdf.pages[2:]
            pdf.save(work)
        return work

    def mediaboxes(self, path):
        with pikepdf.open(path) as pdf:
            return [tuple(round(float(v), 1) for v in page.mediabox) for page in pdf.pages]

    def test_pages_are_resized_to_the_target_dimensions(self, source, tmp_path):
        out = tmp_path / 'cropped.pdf'
        create_pdf_from_cropped_pages(str(source), str(out), (1684.0, 1190.0))
        assert self.mediaboxes(out) == [(0.0, 0.0, 1684.0, 1190.0)] * 2

    def test_without_a_target_the_pages_shrink_to_the_detected_border(self, source, tmp_path):
        before = self.mediaboxes(source)
        out = tmp_path / 'cropped.pdf'
        create_pdf_from_cropped_pages(str(source), str(out), (None, None))
        after = self.mediaboxes(out)

        assert len(after) == len(before)
        for (_, _, w_before, h_before), (_, _, w_after, h_after) in zip(before, after):
            assert 0 < w_after <= w_before and 0 < h_after <= h_before

    def test_the_source_is_renamed_out_of_the_way(self, source, tmp_path):
        out = tmp_path / 'cropped.pdf'
        create_pdf_from_cropped_pages(str(source), str(out), (None, None))
        assert not source.exists()
        assert source.with_suffix('.pdf.tmp').is_file()

    def test_rotation_is_baked_into_the_output(self, tmp_path):
        work = tmp_path / 'rot.pdf'
        with pikepdf.open(DRAWING) as pdf:
            del pdf.pages[1:]
            for page in pdf.pages:
                page.rotate(90, False)
            pdf.save(work)
        out = tmp_path / 'cropped.pdf'
        create_pdf_from_cropped_pages(str(work), str(out), (None, None))

        with pikepdf.open(out) as pdf:
            assert [page.rotation for page in pdf.pages] == [0]
            width = float(pdf.pages[0].mediabox[2]) - float(pdf.pages[0].mediabox[0])
            height = float(pdf.pages[0].mediabox[3]) - float(pdf.pages[0].mediabox[1])
        assert height > width, 'a 90 degree rotated landscape page crops to a portrait box'
