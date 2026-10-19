"""Unit tests for bin/logic_validators.py — pure regex validators only."""

import pytest

from bin.logic_validators import Validators


class TestCheckObjectNameAcmValid:
    @pytest.mark.parametrize("name", [
        "Object1",
        "Valve",
        "_leading_underscore",
        "Pump_101",
        "A",
        "TIC_401_Val",
    ])
    def test_accepts_valid_acm_names(self, name):
        assert Validators.check_object_name_acm_valid(name) is True

    @pytest.mark.parametrize("name", [
        "1Object",          # must not start with a digit
        "Object__1",        # no double underscore
        "Object_",          # no trailing underscore
        "Object-1",         # hyphen is not allowed
        "Object 1",         # space is not allowed
        "Object.1",         # dot is not allowed
        "",                 # empty
        "Objeçt",           # non-ascii
    ])
    def test_rejects_invalid_acm_names(self, name):
        assert Validators.check_object_name_acm_valid(name) is False


class TestProjectNameValidator:
    @pytest.mark.parametrize("name", [
        "MyProject",
        "My Project",
        "project.v2",
        "Project_1",
        "123",
    ])
    def test_accepts_word_dot_and_space(self, name):
        assert Validators.project_name_validator(name) is True

    @pytest.mark.parametrize("name", [
        "bad/name",
        "bad\\name",
        "bad:name",
        "bad*name",
        "bad?name",
        'bad"name',
        "bad<name>",
        "bad|name",
    ])
    def test_rejects_path_and_wildcard_characters(self, name):
        assert Validators.project_name_validator(name) is False

    def test_empty_string_is_allowed_so_the_entry_box_can_be_cleared(self):
        # Deliberate carve-out: the validator runs on every keystroke.
        assert Validators.project_name_validator("") is True


class TestCheckProjectNameValid:
    @pytest.mark.parametrize("name,expected", [
        ("MyProject", True),
        ("", False),
        (None, False),
    ])
    def test_rejects_only_falsy_names(self, name, expected):
        assert Validators.check_project_name_valid(name) is expected


class TestCheckHexRgbColor:
    @pytest.mark.parametrize("value", ["AABBCC", "aabbcc", "AaBbCc", "FFF", "000", "000000", "0b84fd"])
    def test_accepts_three_or_six_hex_digits(self, value):
        assert Validators.check_hex_rgb_color(value) is True

    @pytest.mark.parametrize("value", [
        "#AABBCC",   # the leading hash is NOT accepted by this validator
        "AABBC",     # 5 digits
        "AABBCCD",   # 7 digits
        "GGHHII",    # non-hex letters
        "",
        " AABBCC",
        "AABBCC ",
    ])
    def test_rejects_everything_else(self, value):
        assert Validators.check_hex_rgb_color(value) is False

    def test_known_quirk_trailing_newline_is_accepted(self):
        # The pattern anchors with `$`, which matches before a final newline.
        # Tighten to `\Z` if a trailing newline should ever be rejected.
        assert Validators.check_hex_rgb_color("AABBCC\n") is True

    def test_config_defaults_are_valid_colors(self):
        # These defaults are written into config.ini by logic_config.Config.
        for default in ("CCCCCC", "AAAAAA", "0B84FD"):
            assert Validators.check_hex_rgb_color(default) is True


class TestCheckEmail:
    @pytest.mark.parametrize("email", [
        "joe@example.com",
        "first.last@sub.domain.co.za",
        "user+tag@example.io",
        "user_name@example-host.com",
    ])
    def test_accepts_valid_addresses(self, email):
        assert Validators.check_email(email) is True

    @pytest.mark.parametrize("email", [
        "joe@example",       # no TLD
        "joe.example.com",   # no @
        "@example.com",      # no local part
        "joe@.com",
        "joe @example.com",
        "",
    ])
    def test_rejects_invalid_addresses(self, email):
        assert Validators.check_email(email) is False


class TestFileTypeCheckersRejectMissingFiles:
    """These wrap PIL/pypdfium2/openpyxl in bare try/except and must never raise."""

    def test_check_image_on_missing_path(self, tmp_path):
        assert Validators.check_image(str(tmp_path / "nope.png")) is False

    def test_check_pdf_on_missing_path(self, tmp_path):
        assert Validators.check_pdf(str(tmp_path / "nope.pdf")) is False

    def test_check_sheet_on_missing_path(self, tmp_path):
        assert Validators.check_sheet(str(tmp_path / "nope.xlsx")) is False

    def test_check_pdf_rejects_a_text_file_named_pdf(self, tmp_path):
        fake = tmp_path / "fake.pdf"
        fake.write_text("this is not a pdf")
        assert Validators.check_pdf(str(fake)) is False

    def test_check_image_accepts_a_real_png(self, tmp_path):
        from PIL import Image

        png = tmp_path / "real.png"
        Image.new("RGB", (4, 4), "white").save(png)
        assert Validators.check_image(str(png)) is True


class TestCheckImageOrPdf:
    def test_accepts_a_real_png(self, tmp_path):
        from PIL import Image

        png = tmp_path / "real.png"
        Image.new("RGB", (4, 4), "white").save(png)
        assert Validators.check_image_or_pdf(str(png)) is True

    def test_accepts_a_real_pdf(self, tmp_path):
        import pikepdf

        pdf = tmp_path / "real.pdf"
        with pikepdf.Pdf.new() as doc:
            doc.add_blank_page()
            doc.save(str(pdf))
        assert Validators.check_image_or_pdf(str(pdf)) is True

    def test_rejects_a_text_file_named_pdf(self, tmp_path):
        fake = tmp_path / "fake.pdf"
        fake.write_text("this is not a pdf")
        assert Validators.check_image_or_pdf(str(fake)) is False

    def test_rejects_a_missing_file(self, tmp_path):
        assert Validators.check_image_or_pdf(str(tmp_path / "nope.png")) is False

    def test_extension_case_is_ignored(self, tmp_path):
        import pikepdf

        pdf = tmp_path / "real.PDF"
        with pikepdf.Pdf.new() as doc:
            doc.add_blank_page()
            doc.save(str(pdf))
        assert Validators.check_image_or_pdf(str(pdf)) is True
