"""Integration tests for bin/logic_internal_database.py (TinyDB-backed project store).

The Database builds its path from './projects/<name>/database' relative to the CWD,
so every test runs inside ``tmp_project_root``. The ``db`` fixture closes the handle
in teardown, which also cancels the background flush timer thread.
"""

import json
from pathlib import Path

import pytest

from bin.logic_internal_database import Database

pytestmark = pytest.mark.integration

PROJECT = "TestProject"
DOC_PATH = "./projects/TestProject/drawings/abc/plan.pdf"


@pytest.fixture
def db(tmp_project_root):
    database = Database(PROJECT)
    yield database
    database.close_db()


def control_module(name="CM-1", module_id="cm-id-1", pno=0, path=DOC_PATH, **extra):
    payload = {"id": module_id, "name": name, "pno": pno, "path": path,
               "type": "Valve", "description": "a valve"}
    payload.update(extra)
    return payload


def text_link(link_id="tl-1", **extra):
    payload = {"id": link_id, "text": "TIC-401", "path": DOC_PATH, "pno": 0}
    payload.update(extra)
    return payload


class TestInitialisation:
    def test_creates_the_database_directory(self, tmp_project_root, db):
        assert (tmp_project_root / "projects" / PROJECT / "database").is_dir()

    def test_a_none_project_name_is_a_no_op_and_does_not_raise(self, tmp_project_root):
        assert Database(None) is not None
        assert not (tmp_project_root / "projects" / "None").exists()

    def test_reopening_an_existing_project_preserves_data(self, tmp_project_root):
        first = Database(PROJECT)
        first.insert_project_document("plan.pdf", DOC_PATH, Database.DRAWING)
        first.close_db()

        second = Database(PROJECT)
        try:
            assert len(second.get_project_drawings()) == 1
        finally:
            second.close_db()

    def test_close_db_is_idempotent(self, tmp_project_root):
        database = Database(PROJECT)
        database.close_db()
        database.close_db()

    def test_data_is_flushed_to_disk_on_close(self, tmp_project_root):
        database = Database(PROJECT)
        database.insert_project_document("plan.pdf", DOC_PATH, Database.DRAWING)
        database.close_db()

        raw = json.loads((tmp_project_root / "projects" / PROJECT / "database" / "database.json").read_text())
        assert "documents" in raw


class TestProjectDocuments:
    def test_insert_returns_an_id_and_the_document_is_retrievable(self, db):
        doc_id = db.insert_project_document("plan.pdf", DOC_PATH, Database.DRAWING)

        drawings = db.get_project_drawings()
        assert len(drawings) == 1
        assert drawings[0]["id"] == doc_id
        assert drawings[0]["name"] == "plan.pdf"
        assert drawings[0]["path"] == DOC_PATH

    def test_a_timestamp_is_stamped_on_insert(self, db):
        db.insert_project_document("plan.pdf", DOC_PATH, Database.DRAWING)
        assert db.get_project_drawings()[0]["timestamp"] > 0

    def test_reinserting_the_same_path_upserts_and_keeps_the_id_stable(self, db):
        first_id = db.insert_project_document("plan.pdf", DOC_PATH, Database.DRAWING)
        second_id = db.insert_project_document("plan-renamed.pdf", DOC_PATH, Database.DRAWING)

        assert first_id == second_id
        drawings = db.get_project_drawings()
        assert len(drawings) == 1
        assert drawings[0]["name"] == "plan-renamed.pdf"

    def test_documents_are_partitioned_by_type(self, db):
        db.insert_project_document("a.pdf", "path/a.pdf", Database.DRAWING)
        db.insert_project_document("b.png", "path/b.png", Database.IMAGE)
        db.insert_project_document("c.txt", "path/c.txt", Database.TEXT)
        db.insert_project_document("d.xlsx", "path/d.xlsx", Database.TABLE)

        assert len(db.get_project_drawings()) == 1
        assert len(db.get_project_drawing_images()) == 1
        assert len(db.get_project_texts()) == 1

    def test_delete_by_id(self, db):
        doc_id = db.insert_project_document("plan.pdf", DOC_PATH, Database.DRAWING)
        db.delete_project_document_by_id(doc_id)
        assert db.get_project_drawings() == []

    def test_delete_by_name(self, db):
        db.insert_project_document("plan.pdf", DOC_PATH, Database.DRAWING)
        db.delete_project_document("plan.pdf")
        assert db.get_project_drawings() == []

    def test_deleting_an_unknown_id_is_a_no_op(self, db):
        db.insert_project_document("plan.pdf", DOC_PATH, Database.DRAWING)
        db.delete_project_document_by_id("no-such-id")
        assert len(db.get_project_drawings()) == 1

    def test_deleting_a_document_cascades_to_its_rois(self, db):
        doc_id = db.insert_project_document("plan.pdf", DOC_PATH, Database.DRAWING)
        db.insert_project_document_roi(DOC_PATH, [{"roi-a": [[0, 0], [10, 10]]}])

        db.delete_project_document_by_id(doc_id)

        assert db.get_project_document_roi(DOC_PATH) == []


class TestRegionsOfInterest:
    def test_roi_round_trip(self, db):
        roi = [{"roi-a": [[0, 0], [10, 0], [10, 10], [0, 10]]}]
        db.insert_project_document_roi(DOC_PATH, roi)

        assert db.get_project_document_roi(DOC_PATH) == roi

    def test_unknown_path_returns_an_empty_list(self, db):
        assert db.get_project_document_roi("./nope.pdf") == []

    def test_inserting_again_replaces_the_roi_list(self, db):
        db.insert_project_document_roi(DOC_PATH, [{"roi-a": [[0, 0]]}])
        db.insert_project_document_roi(DOC_PATH, [{"roi-b": [[5, 5]]}])

        stored = db.get_project_document_roi(DOC_PATH)
        assert stored == [{"roi-b": [[5, 5]]}]

    def test_delete_roi_removes_only_the_named_roi_on_that_page(self, db):
        db.insert_project_document_roi(
            DOC_PATH, [{"roi-a": [[0, 0]], "roi-b": [[1, 1]]}, {"roi-c": [[2, 2]]}])

        db.delete_roi(DOC_PATH, 0, "roi-a")

        assert db.get_project_document_roi(DOC_PATH) == [{"roi-b": [[1, 1]]}, {"roi-c": [[2, 2]]}]

    def test_delete_roi_on_an_out_of_range_page_is_a_no_op(self, db):
        db.insert_project_document_roi(DOC_PATH, [{"roi-a": [[0, 0]]}])
        db.delete_roi(DOC_PATH, 99, "roi-a")
        assert db.get_project_document_roi(DOC_PATH) == [{"roi-a": [[0, 0]]}]

    def test_delete_project_document_roi_clears_everything_for_the_path(self, db):
        db.insert_project_document_roi(DOC_PATH, [{"roi-a": [[0, 0]]}])
        db.delete_project_document_roi(DOC_PATH)
        assert db.get_project_document_roi(DOC_PATH) == []


class TestControlModules:
    def test_save_and_get_by_name(self, db):
        db.save_control_module(control_module())
        assert db.get_control_module("CM-1")["id"] == "cm-id-1"

    def test_save_and_get_by_id(self, db):
        db.save_control_module(control_module())
        assert db.get_control_module_by_id("cm-id-1")["name"] == "CM-1"

    def test_unknown_name_returns_an_empty_dict(self, db):
        assert db.get_control_module("nope") == {}

    def test_saving_the_same_id_updates_rather_than_duplicates(self, db):
        db.save_control_module(control_module(name="CM-1"))
        db.save_control_module(control_module(name="CM-1-renamed"))

        assert len(db.get_all_control_modules()) == 1
        assert db.get_control_module("CM-1-renamed")["id"] == "cm-id-1"

    def test_get_all_returns_every_module(self, db):
        db.save_control_module(control_module(name="CM-1", module_id="a"))
        db.save_control_module(control_module(name="CM-2", module_id="b"))

        assert len(db.get_all_control_modules()) == 2

    def test_get_all_on_an_empty_table_is_falsy(self, db):
        assert not db.get_all_control_modules()

    def test_delete_by_name(self, db):
        db.save_control_module(control_module())
        db.delete_control_module("CM-1")
        assert db.get_control_module("CM-1") == {}

    def test_delete_by_id(self, db):
        db.save_control_module(control_module())
        db.delete_control_module_by_id("cm-id-1")
        assert not db.get_all_control_modules()

    def test_modules_are_filtered_by_document(self, db):
        db.save_control_module(control_module(name="CM-1", module_id="a", path="doc-a.pdf"))
        db.save_control_module(control_module(name="CM-2", module_id="b", path="doc-b.pdf"))

        assert len(db.get_all_control_module_in_document("doc-a.pdf")) == 1

    def test_modules_are_filtered_by_page(self, db):
        db.save_control_module(control_module(name="CM-1", module_id="a", pno=0))
        db.save_control_module(control_module(name="CM-2", module_id="b", pno=1))

        assert len(db.get_all_control_module_on_page(DOC_PATH, 1)) == 1


class TestTextLinkStateMachine:
    """An id must live in at most one of unapproved / approved / rejected."""

    def test_unapproved_round_trip(self, db):
        db.save_unapproved_text_link(text_link())
        links = db.get_all_unapproved_text_links()
        assert len(links) == 1
        assert links[0]["text"] == "TIC-401"

    def test_approving_removes_it_from_unapproved(self, db):
        db.save_unapproved_text_link(text_link())
        db.save_approved_text_link(text_link())

        assert not db.get_all_unapproved_text_links()

    def test_rejecting_removes_it_from_unapproved(self, db):
        db.save_unapproved_text_link(text_link())
        db.save_rejected_text_link(text_link())

        assert not db.get_all_unapproved_text_links()

    def test_delete_removes_it_from_every_table(self, db):
        db.save_unapproved_text_link(text_link())
        db.save_approved_text_link(text_link())
        db.delete_text_link("tl-1")

        assert not db.get_all_unapproved_text_links()

    def test_saving_the_same_id_twice_does_not_duplicate(self, db):
        db.save_unapproved_text_link(text_link(text="first"))
        db.save_unapproved_text_link(text_link(text="second"))

        links = db.get_all_unapproved_text_links()
        assert len(links) == 1
        assert links[0]["text"] == "second"

    def test_a_subobject_link_gets_a_display_name_stamped(self, db):
        db.save_unapproved_text_link(text_link(subobject="Motor"))
        assert db.get_all_unapproved_text_links()[0]["subobject_name"].endswith("*")


class TestSubscribers:
    def test_document_viewer_is_notified_on_roi_insert(self, db):
        seen = []
        db.subscribe_to_changes_for_document_viewer(seen.append)

        db.insert_project_document_roi(DOC_PATH, [{"roi-a": [[0, 0]]}])

        assert seen == [DOC_PATH]

    def test_tool_viewer_is_notified_on_roi_delete(self, db):
        seen = []
        db.subscribe_to_changes_for_tool_viewer(lambda path, roi_id: seen.append((path, roi_id)))
        db.insert_project_document_roi(DOC_PATH, [{"roi-a": [[0, 0]]}])

        db.delete_roi(DOC_PATH, 0, "roi-a")

        assert seen == [(DOC_PATH, "roi-a")]

    def test_subscribing_seeds_the_callback_once_immediately(self, db):
        calls = []
        db.subscribe_unapproved_text_link_update(lambda: calls.append("changed"))
        assert len(calls) == 1

    def test_unapproved_text_link_subscribers_fire_on_save_and_delete(self, db):
        calls = []
        db.subscribe_unapproved_text_link_update(lambda: calls.append("changed"))
        calls.clear()  # drop the seeding call made at subscription time

        db.save_unapproved_text_link(text_link())
        db.delete_text_link("tl-1")

        assert len(calls) == 2

    def test_a_raising_subscriber_does_not_break_the_write(self, db):
        def boom():
            raise RuntimeError("subscriber exploded")

        db.subscribe_unapproved_text_link_update(boom)
        db.save_unapproved_text_link(text_link())

        assert len(db.get_all_unapproved_text_links()) == 1

    def test_hmi_display_subscriber_is_scoped_to_its_page(self, db):
        seen = []
        db.subscribe_to_element_updates_on_hmi_display(
            lambda payload, kind: seen.append(kind), DOC_PATH, 0)

        db.save_control_module(control_module(pno=0))
        db.save_control_module(control_module(name="CM-2", module_id="b", pno=7))

        assert seen == ["control_module"]


class TestLazyMigrations:
    def test_legacy_documents_without_an_id_are_stamped_on_open(self, tmp_project_root):
        db_dir = tmp_project_root / "projects" / PROJECT / "database"
        db_dir.mkdir(parents=True)
        (db_dir / "database.json").write_text(json.dumps({
            "documents": {"1": {"name": "legacy.pdf", "path": DOC_PATH, "type": "DRAWING", "timestamp": 1}}
        }))

        database = Database(PROJECT)
        try:
            assert "id" in database.get_project_drawings()[0]
        finally:
            database.close_db()

    def test_an_id_in_both_approved_and_rejected_is_reconciled_to_the_newer_one(self, tmp_project_root):
        db_dir = tmp_project_root / "projects" / PROJECT / "database"
        db_dir.mkdir(parents=True)
        (db_dir / "database.json").write_text(json.dumps({
            "approved_text_links": {"1": {"id": "dup", "timestamp": 200}},
            "rejected_text_links": {"1": {"id": "dup", "timestamp": 100}},
        }))

        database = Database(PROJECT)
        try:
            database.close_db()
        finally:
            pass

        raw = json.loads((db_dir / "database.json").read_text())
        assert raw.get("rejected_text_links", {}) == {}
        assert list(raw["approved_text_links"].values())[0]["id"] == "dup"


class TestImportedLinkedTextRegexes:
    """A shared project archive carries database.json verbatim; its link strings are untrusted."""

    def test_malicious_regex_row_is_rejected_without_executing(self, tmp_project_root):
        from bin.logic_linked_texts import LinkedText, LinkedTextDecodeError

        marker = tmp_project_root / "pwned"
        payload = "__import__('pathlib').Path(%r).write_text('x')" % str(marker)
        row = {"id": "evil", "text_relationship": "in_line", "template_id": "t", "parameters": {},
               "tagname": {"text": "TIC", "text_type": "object", "object_type": None, "linked": True,
                           "given_text": "None", "links": payload, "reftype": None,
                           "link_type": "text", "axis": 0}}
        db_dir = tmp_project_root / "projects" / PROJECT / "database"
        db_dir.mkdir(parents=True)
        (db_dir / "database.json").write_text(json.dumps({"linked_text_regexes": {"1": row}}))

        database = Database(PROJECT)
        try:
            rows = database.get_all_linked_text_regexes()
        finally:
            database.close_db()

        assert rows and rows[0]["id"] == "evil"
        with pytest.raises(LinkedTextDecodeError):
            LinkedText.from_dict(rows[0]["tagname"])
        assert not marker.exists()
