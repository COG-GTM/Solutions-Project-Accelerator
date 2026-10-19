"""Integration tests for bin/logic_file_manager.py.

Every path in Project_File_Manager is built from './projects/' relative to the
current working directory, so all tests run inside ``tmp_project_root``.

Note: these methods are wrapped in ``@handle_exception_with_messagebox()``, which
swallows exceptions and returns ``None``. Failure cases are therefore asserted on
the return value and on the dialogs captured by the autouse ``captured_dialogs``
fixture, never with ``pytest.raises``.
"""

import os
from pathlib import Path

import pytest

from bin.logic_file_manager import Project_File_Manager

pytestmark = pytest.mark.integration


@pytest.fixture
def png_factory(tmp_path):
    from PIL import Image

    def make(name, colour="white"):
        target = tmp_path / "src" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8), colour).save(target)
        return str(target)

    return make


@pytest.fixture
def pdf_factory(tmp_path):
    import pikepdf

    def make(name, pages=1):
        target = tmp_path / "src" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with pikepdf.Pdf.new() as doc:
            for _ in range(pages):
                doc.add_blank_page()
            doc.save(str(target))
        return str(target)

    return make


class TestCreateProject:
    def test_creates_the_directory_and_returns_the_name(self, tmp_project_root):
        result = Project_File_Manager.create_project("MyProject", "A description", "1.0")
        assert result == "MyProject"
        assert (tmp_project_root / "projects" / "MyProject").is_dir()

    def test_writes_a_project_ini_with_the_supplied_metadata(self, tmp_project_root):
        Project_File_Manager.create_project("MyProject", "A description", "1.0")

        name, description = Project_File_Manager.get_project_details("MyProject")
        assert name == "MyProject"
        assert description == "A description"

    def test_ini_contains_the_version(self, tmp_project_root):
        Project_File_Manager.create_project("MyProject", "A description", "2.5")
        text = (tmp_project_root / "projects" / "MyProject" / "project.ini").read_text()
        assert "2.5" in text

    def test_recreating_an_existing_project_overwrites_the_metadata(self, tmp_project_root):
        Project_File_Manager.create_project("MyProject", "first", "1.0")
        Project_File_Manager.create_project("MyProject", "second", "2.0")

        _, description = Project_File_Manager.get_project_details("MyProject")
        assert description == "second"

    def test_project_names_with_spaces_are_supported(self, tmp_project_root):
        Project_File_Manager.create_project("My Project", "desc", "1.0")
        assert (tmp_project_root / "projects" / "My Project").is_dir()


class TestGetAllProjects:
    def test_empty_when_nothing_has_been_created(self, tmp_project_root):
        assert Project_File_Manager.get_all_projects() == []

    def test_lists_every_created_project(self, tmp_project_root):
        for name in ("Alpha", "Beta", "Gamma"):
            Project_File_Manager.create_project(name, "d", "1.0")

        assert sorted(Project_File_Manager.get_all_projects()) == ["Alpha", "Beta", "Gamma"]

    def test_does_not_recurse_into_project_subfolders(self, tmp_project_root, pdf_factory):
        Project_File_Manager.create_project("Alpha", "d", "1.0")
        Project_File_Manager.import_drawing_file(pdf_factory("a.pdf"), "Alpha")

        assert Project_File_Manager.get_all_projects() == ["Alpha"]


class TestImportDrawingFile:
    def test_pdf_is_copied_into_a_uuid_folder(self, tmp_project_root, pdf_factory):
        Project_File_Manager.create_project("P", "d", "1.0")
        source = pdf_factory("drawing.pdf")

        destination = Project_File_Manager.import_drawing_file(source, "P")

        assert destination.startswith("./projects/P/drawings/")
        assert (Path(destination) / "drawing.pdf").is_file()

    def test_source_file_is_left_in_place(self, tmp_project_root, pdf_factory):
        Project_File_Manager.create_project("P", "d", "1.0")
        source = pdf_factory("drawing.pdf")

        Project_File_Manager.import_drawing_file(source, "P")

        assert os.path.isfile(source)

    def test_images_are_renamed_to_zero_inside_an_images_folder(self, tmp_project_root, png_factory):
        Project_File_Manager.create_project("P", "d", "1.0")
        source = png_factory("photo.png")

        destination = Project_File_Manager.import_drawing_file(source, "P")

        assert destination.endswith("/images")
        assert (Path(destination) / "0.png").is_file()

    def test_two_imports_land_in_different_folders(self, tmp_project_root, pdf_factory):
        Project_File_Manager.create_project("P", "d", "1.0")

        first = Project_File_Manager.import_drawing_file(pdf_factory("a.pdf"), "P")
        second = Project_File_Manager.import_drawing_file(pdf_factory("b.pdf"), "P")

        assert first != second

    @pytest.mark.parametrize("extension", [".jpg", ".jpeg"])
    def test_jpeg_variants_are_treated_as_images(self, tmp_project_root, png_factory, extension):
        Project_File_Manager.create_project("P", "d", "1.0")
        source = png_factory(f"photo{extension}")

        destination = Project_File_Manager.import_drawing_file(source, "P")

        assert (Path(destination) / f"0{extension}").is_file()

    def test_unsupported_extension_returns_none(self, tmp_project_root, tmp_path):
        Project_File_Manager.create_project("P", "d", "1.0")
        source = tmp_path / "notes.txt"
        source.write_text("hello")

        assert Project_File_Manager.import_drawing_file(str(source), "P") is None

    def test_missing_source_is_reported_through_a_dialog_not_an_exception(
        self, tmp_project_root, captured_dialogs
    ):
        Project_File_Manager.create_project("P", "d", "1.0")

        result = Project_File_Manager.import_drawing_file("./does/not/exist.pdf", "P")

        assert result is None
        assert captured_dialogs["error"], "expected the messagebox error path to be taken"


class TestCombineDrawingFiles:
    def test_pdfs_are_merged_and_page_counts_add_up(self, tmp_project_root, pdf_factory):
        import pikepdf

        Project_File_Manager.create_project("P", "d", "1.0")
        files = [pdf_factory("a.pdf", pages=2), pdf_factory("b.pdf", pages=3)]

        destination, filename = Project_File_Manager.combine_drawing_files(files, "P")

        merged = Path(destination) / filename
        assert merged.is_file()
        with pikepdf.open(str(merged)) as doc:
            assert len(doc.pages) == 5

    def test_merged_pdf_is_named_with_the_combined_prefix(self, tmp_project_root, pdf_factory):
        Project_File_Manager.create_project("P", "d", "1.0")
        _, filename = Project_File_Manager.combine_drawing_files(
            [pdf_factory("a.pdf"), pdf_factory("b.pdf")], "P")

        assert filename.startswith("Combined_PDF_")
        assert filename.endswith(".pdf")

    def test_images_are_renumbered_sequentially(self, tmp_project_root, png_factory):
        Project_File_Manager.create_project("P", "d", "1.0")
        files = [png_factory("x.png"), png_factory("y.png"), png_factory("z.png")]

        destination, filename = Project_File_Manager.combine_drawing_files(files, "P")

        assert filename.startswith("Combined_Images_")
        assert sorted(os.listdir(destination)) == ["0.png", "1.png", "2.png"]

    def test_image_ordering_follows_the_input_list(self, tmp_project_root, png_factory):
        from PIL import Image

        Project_File_Manager.create_project("P", "d", "1.0")
        files = [png_factory("red.png", "red"), png_factory("blue.png", "blue")]

        destination, _ = Project_File_Manager.combine_drawing_files(files, "P")

        assert Image.open(Path(destination) / "0.png").getpixel((0, 0)) == (255, 0, 0)
        assert Image.open(Path(destination) / "1.png").getpixel((0, 0)) == (0, 0, 255)


class TestImportPdfAsImages:
    @pytest.fixture
    def colour_pdf_factory(self, tmp_path):
        import pikepdf

        def make(name, page_colours):
            target = tmp_path / "src" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with pikepdf.Pdf.new() as doc:
                for colour in page_colours:
                    page = pikepdf.Page(doc.add_blank_page(page_size=(72, 72)))
                    page.contents_add('{} {} {} rg 0 0 72 72 re f\n'.format(*colour).encode())
                doc.save(str(target))
            return str(target)

        return make

    def test_one_zero_padded_png_per_page(self, tmp_project_root, pdf_factory):
        Project_File_Manager.create_project("P", "d", "1.0")

        destination, _ = Project_File_Manager.import_pdf_as_images([pdf_factory("a.pdf", pages=3)], "P")

        assert destination.endswith("/images")
        assert sorted(os.listdir(destination)) == ["0000.png", "0001.png", "0002.png"]

    def test_colours_are_preserved(self, tmp_project_root, colour_pdf_factory):
        from PIL import Image

        Project_File_Manager.create_project("P", "d", "1.0")
        source = colour_pdf_factory("colour.pdf", [(1, 0, 0)])

        destination, _ = Project_File_Manager.import_pdf_as_images([source], "P")

        rendered = Image.open(Path(destination) / "0000.png")
        assert rendered.mode == "RGB"
        red, green, blue = rendered.getpixel((36, 36))
        assert red > 200 and green < 60 and blue < 60

    def test_pages_keep_their_order_across_multiple_pdfs(self, tmp_project_root, colour_pdf_factory):
        from PIL import Image

        Project_File_Manager.create_project("P", "d", "1.0")
        files = [colour_pdf_factory("red.pdf", [(1, 0, 0)]),
                 colour_pdf_factory("blue.pdf", [(0, 0, 1)])]

        destination, _ = Project_File_Manager.import_pdf_as_images(files, "P")

        assert Image.open(Path(destination) / "0000.png").getpixel((36, 36))[0] > 200
        assert Image.open(Path(destination) / "0001.png").getpixel((36, 36))[2] > 200

    def test_more_than_ten_pages_sort_correctly(self, tmp_project_root, pdf_factory):
        Project_File_Manager.create_project("P", "d", "1.0")

        destination, _ = Project_File_Manager.import_pdf_as_images([pdf_factory("a.pdf", pages=12)], "P")

        found = Project_File_Manager.get_drawing_image_files(destination)
        assert [os.path.basename(f) for f in found] == [f"{i:04d}.png" for i in range(12)]

    def test_single_pdf_keeps_its_file_name(self, tmp_project_root, pdf_factory):
        Project_File_Manager.create_project("P", "d", "1.0")

        _, filename = Project_File_Manager.import_pdf_as_images([pdf_factory("drawing.pdf")], "P")

        assert filename == "drawing.pdf"

    def test_multiple_pdfs_use_the_combined_prefix(self, tmp_project_root, pdf_factory):
        Project_File_Manager.create_project("P", "d", "1.0")

        _, filename = Project_File_Manager.import_pdf_as_images(
            [pdf_factory("a.pdf"), pdf_factory("b.pdf")], "P")

        assert filename.startswith("Combined_Images_")

    def test_zoom_scales_the_rendered_page(self, tmp_project_root, colour_pdf_factory):
        from PIL import Image

        Project_File_Manager.create_project("P", "d", "1.0")
        source = colour_pdf_factory("colour.pdf", [(1, 0, 0)])

        destination, _ = Project_File_Manager.import_pdf_as_images([source], "P", zoom=2.0)

        assert Image.open(Path(destination) / "0000.png").size == (144, 144)

    def test_default_zoom_is_two(self, tmp_project_root, colour_pdf_factory):
        from PIL import Image

        Project_File_Manager.create_project("P", "d", "1.0")
        source = colour_pdf_factory("colour.pdf", [(1, 0, 0)])

        destination, _ = Project_File_Manager.import_pdf_as_images([source], "P")

        assert Image.open(Path(destination) / "0000.png").size == (144, 144)

    def test_page_callback_reports_progress(self, tmp_project_root, pdf_factory):
        Project_File_Manager.create_project("P", "d", "1.0")
        seen = []

        Project_File_Manager.import_pdf_as_images(
            [pdf_factory("a.pdf", pages=2), pdf_factory("b.pdf", pages=1)], "P",
            page_callback=lambda done, total: seen.append((done, total)))

        assert seen == [(1, 3), (2, 3), (3, 3)]

    def test_cancelling_returns_none_and_removes_the_folder(self, tmp_project_root, pdf_factory):
        Project_File_Manager.create_project("P", "d", "1.0")

        result = Project_File_Manager.import_pdf_as_images(
            [pdf_factory("a.pdf", pages=4)], "P", page_callback=lambda done, total: done == 2)

        assert result is None
        assert Project_File_Manager.get_all_projects() == ["P"]
        assert list((tmp_project_root / "projects" / "P" / "drawings").iterdir()) == []

    def test_missing_source_is_reported_through_a_dialog_not_an_exception(
        self, tmp_project_root, captured_dialogs
    ):
        Project_File_Manager.create_project("P", "d", "1.0")

        result = Project_File_Manager.import_pdf_as_images(["./does/not/exist.pdf"], "P")

        assert result is None
        assert captured_dialogs["error"], "expected the messagebox error path to be taken"


class TestGetDrawingImageFiles:
    def test_returns_files_in_sorted_order(self, tmp_project_root, png_factory):
        Project_File_Manager.create_project("P", "d", "1.0")
        destination, _ = Project_File_Manager.combine_drawing_files(
            [png_factory("a.png"), png_factory("b.png")], "P")

        found = Project_File_Manager.get_drawing_image_files(destination)
        assert [os.path.basename(f) for f in found] == ["0.png", "1.png"]

    def test_empty_directory_yields_an_empty_list(self, tmp_project_root):
        empty = tmp_project_root / "empty"
        empty.mkdir()
        assert Project_File_Manager.get_drawing_image_files(str(empty)) == []


class TestDeleteDocumentFile:
    def test_removes_the_imported_folder(self, tmp_project_root, pdf_factory):
        Project_File_Manager.create_project("P", "d", "1.0")
        destination = Project_File_Manager.import_drawing_file(pdf_factory("a.pdf"), "P")

        Project_File_Manager.delete_document_file(destination)

        assert not os.path.exists(destination)

    def test_deleting_a_missing_folder_is_reported_not_raised(
        self, tmp_project_root, captured_dialogs
    ):
        Project_File_Manager.delete_document_file("./projects/P/drawings/nope")
        assert captured_dialogs["error"]
