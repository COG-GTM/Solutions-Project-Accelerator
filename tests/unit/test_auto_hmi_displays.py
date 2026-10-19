"""Auto-created HMI displays for projects where the user never defined any.

Covers ``bin.logic_tools.acm_safe_display_name`` and
``bin.logic_tools.auto_create_hmi_displays_for_scanned_pages``, which back the
"generate displays anyway" path of Tools > Build HMI.
"""

import pytest

from bin.logic_internal_database import Database
from bin.logic_tools import (acm_safe_display_name,
                             auto_create_hmi_displays_for_scanned_pages,
                             build_auto_hmi_display,
                             find_pages_needing_hmi_displays)
from bin.logic_validators import Validators

DRAWING_PATH = "C:/drawings/55-P&ID Rev.2.pdf"


@pytest.fixture
def db(tmp_project_root):
    database = Database("auto_display_project")
    yield database
    database.close_db()


def _add_control_module(database, path, pno, name):
    database.save_control_module({"id": f"{path}-{pno}-{name}", "path": path, "pno": pno, "name": name})


class TestAcmSafeDisplayName:

    def test_sanitises_filename_and_appends_one_based_page(self):
        assert acm_safe_display_name(DRAWING_PATH, 2, set()) == "D_55_P_ID_Rev_2_P3"

    @pytest.mark.parametrize("path", [DRAWING_PATH, "C:/d/__weird__.pdf", "C:/d/2024.pdf", "C:/d/___.pdf"])
    def test_result_is_acm_compliant(self, path):
        assert Validators.check_object_name_acm_valid(acm_safe_display_name(path, 0, set()))

    def test_unnamed_file_falls_back_to_display(self):
        assert acm_safe_display_name("C:/d/___.pdf", 0, set()) == "Display_P1"

    def test_collisions_get_a_numeric_suffix(self):
        taken = set()
        first = acm_safe_display_name(DRAWING_PATH, 0, taken)
        second = acm_safe_display_name(DRAWING_PATH, 0, taken)
        third = acm_safe_display_name(DRAWING_PATH, 0, taken)
        assert [first, second, third] == ["D_55_P_ID_Rev_2_P1", "D_55_P_ID_Rev_2_P1_2", "D_55_P_ID_Rev_2_P1_3"]

    def test_existing_names_are_matched_case_insensitively(self):
        assert acm_safe_display_name(DRAWING_PATH, 0, {"d_55_p_id_rev_2_p1"}) == "D_55_P_ID_Rev_2_P1_2"


class TestBuildAutoHmiDisplay:

    def test_linked_graphics_are_empty_because_nothing_was_drawn(self):
        display = build_auto_hmi_display("Sheet_P1", DRAWING_PATH, 0)
        assert display["primary_linked_graphic"] == {}
        assert display["secondary_linked_graphic"] == {}
        assert display["page_links"] == []

    def test_id_is_unique_per_display_name(self):
        first = build_auto_hmi_display("Sheet_P1", DRAWING_PATH, 0)
        second = build_auto_hmi_display("Other_P1", DRAWING_PATH, 0)
        assert first["id"] != second["id"]


class TestFindPagesNeedingHmiDisplays:

    def test_lists_only_pages_with_content_and_no_display(self, db):
        db.insert_project_document("55-P&ID Rev.2.pdf", DRAWING_PATH, Database.DRAWING)
        _add_control_module(db, DRAWING_PATH, 0, "PU_101")
        _add_control_module(db, DRAWING_PATH, 2, "PU_301")
        db.save_hmi_display({"id": "user-drawn", "name": "Overview", "path": DRAWING_PATH, "pno": 0})

        assert find_pages_needing_hmi_displays(db) == [(DRAWING_PATH, 2)]

    def test_is_empty_when_nothing_was_scanned(self, db):
        db.insert_project_document("55-P&ID Rev.2.pdf", DRAWING_PATH, Database.DRAWING)

        assert find_pages_needing_hmi_displays(db) == []


class TestAutoCreateHmiDisplaysForScannedPages:

    def test_creates_one_display_per_page_holding_content(self, db):
        db.insert_project_document("55-P&ID Rev.2.pdf", DRAWING_PATH, Database.DRAWING)
        _add_control_module(db, DRAWING_PATH, 0, "PU_101")
        _add_control_module(db, DRAWING_PATH, 0, "PU_102")
        _add_control_module(db, DRAWING_PATH, 3, "PU_401")

        created = auto_create_hmi_displays_for_scanned_pages(db)

        assert created == ["D_55_P_ID_Rev_2_P1", "D_55_P_ID_Rev_2_P4"]
        assert [display["pno"] for display in db.get_all_hmi_displays()] == [0, 3]

    def test_ignores_pages_without_content(self, db):
        db.insert_project_document("55-P&ID Rev.2.pdf", DRAWING_PATH, Database.DRAWING)
        _add_control_module(db, DRAWING_PATH, 1, "PU_201")

        auto_create_hmi_displays_for_scanned_pages(db)

        assert len(db.get_all_hmi_displays_on_page(DRAWING_PATH, 0)) == 0
        assert len(db.get_all_hmi_displays_on_page(DRAWING_PATH, 1)) == 1

    def test_is_idempotent(self, db):
        db.insert_project_document("55-P&ID Rev.2.pdf", DRAWING_PATH, Database.DRAWING)
        _add_control_module(db, DRAWING_PATH, 0, "PU_101")

        auto_create_hmi_displays_for_scanned_pages(db)
        assert auto_create_hmi_displays_for_scanned_pages(db) == []
        assert len(db.get_all_hmi_displays()) == 1

    def test_leaves_pages_the_user_already_defined_alone(self, db):
        db.insert_project_document("55-P&ID Rev.2.pdf", DRAWING_PATH, Database.DRAWING)
        _add_control_module(db, DRAWING_PATH, 0, "PU_101")
        _add_control_module(db, DRAWING_PATH, 1, "PU_201")
        db.save_hmi_display({"id": "user-drawn", "name": "Overview", "path": DRAWING_PATH, "pno": 0})

        created = auto_create_hmi_displays_for_scanned_pages(db)

        assert created == ["D_55_P_ID_Rev_2_P2"]

    def test_returns_nothing_when_no_document_was_scanned(self, db):
        assert auto_create_hmi_displays_for_scanned_pages(db) == []
