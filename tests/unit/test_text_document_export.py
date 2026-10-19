"""Unit tests for the text-document export-with-data path in bin/logic_tools.py."""

import pytest

from bin.logic_internal_database import Database
from bin.logic_tools import (
    TEXT_LINK_HEADERS,
    export_text_excel_with_data,
    write_text_link_rows,
)

DOCUMENT = 'projects/P/texts/spec.pdf'
WORKSHEET_NAMES = ['Approved Links', 'Unapproved Links', 'Rejected Links']


class FakeExcelExporter:
    def __init__(self, filename=None):
        self.filename = filename
        self.headers = {}
        self.rows = {}
        self.closed = False

    def add_worksheet_with_headers(self, worksheet_name, headers):
        self.headers.setdefault(worksheet_name, headers)
        self.rows.setdefault(worksheet_name, {})

    def get_next_row(self, worksheet_name):
        return len(self.rows[worksheet_name]) + 1

    def write_to_cell(self, worksheet_name, row, column, value, percentage=False):
        self.rows[worksheet_name].setdefault(row, {})[column] = value

    def close(self):
        self.closed = True

    def row_values(self, worksheet_name, row):
        cells = self.rows[worksheet_name][row]
        return [cells[column] for column in sorted(cells)]


class FakeDatabase:
    def __init__(self, approved=(), unapproved=(), rejected=()):
        self.approved = list(approved)
        self.unapproved = list(unapproved)
        self.rejected = list(rejected)

    def get_all_approved_text_links_by_document(self, path):
        return self.approved

    def get_all_unapproved_text_links_by_document(self, path):
        return self.unapproved

    def get_all_rejected_text_links_by_document(self, path):
        return self.rejected


def make_text_link(tagname='TIC-401', parameters=None, pno=0, **overrides):
    link = {
        'id': tagname,
        'path': DOCUMENT,
        'pno': pno,
        'tagname': {'text': tagname},
        'parameters': parameters if parameters is not None else {'PV_EU': {'text': 'degC'}},
        'is_llm_generated': False,
    }
    link.update(overrides)
    return link


def never_stop(textbox_entry, label_text, percentage):
    return False


class TestWriteTextLinkRows:
    def test_writes_one_row_per_parameter(self):
        exporter = FakeExcelExporter()
        exporter.add_worksheet_with_headers('Approved Links', TEXT_LINK_HEADERS)

        link = make_text_link(parameters={'PV_EU': {'text': 'degC'}, 'PV_Max': {'text': '150'}})
        write_text_link_rows(exporter, 'Approved Links', link, DOCUMENT)

        assert len(exporter.rows['Approved Links']) == 2
        assert exporter.row_values('Approved Links', 1) == [
            'TIC-401', '', 'PV_EU', 'degC', 'spec.pdf', 1, 'False']
        assert exporter.row_values('Approved Links', 2)[2:4] == ['PV_Max', '150']

    def test_writes_single_row_when_link_has_no_parameters(self):
        exporter = FakeExcelExporter()
        exporter.add_worksheet_with_headers('Approved Links', TEXT_LINK_HEADERS)

        write_text_link_rows(exporter, 'Approved Links', make_text_link(parameters={}), DOCUMENT)

        assert exporter.row_values('Approved Links', 1) == [
            'TIC-401', '', '', '', 'spec.pdf', 1, 'False']

    def test_includes_subobject_and_llm_flag(self):
        exporter = FakeExcelExporter()
        exporter.add_worksheet_with_headers('Approved Links', TEXT_LINK_HEADERS)

        link = make_text_link(subobject_name='Alarm1', is_llm_generated=True)
        write_text_link_rows(exporter, 'Approved Links', link, DOCUMENT)

        assert exporter.row_values('Approved Links', 1)[1] == 'Alarm1'
        assert exporter.row_values('Approved Links', 1)[6] == 'True'

    def test_missing_page_number_is_blank(self):
        exporter = FakeExcelExporter()
        exporter.add_worksheet_with_headers('Approved Links', TEXT_LINK_HEADERS)

        write_text_link_rows(exporter, 'Approved Links', make_text_link(pno=None), DOCUMENT)

        assert exporter.row_values('Approved Links', 1)[5] == ''

    def test_returns_tagname_for_the_progress_textbox(self):
        exporter = FakeExcelExporter()
        exporter.add_worksheet_with_headers('Approved Links', TEXT_LINK_HEADERS)

        assert write_text_link_rows(exporter, 'Approved Links', make_text_link(), DOCUMENT) == 'TIC-401'


class TestExportTextExcelWithData:
    @pytest.fixture
    def exporter(self, monkeypatch):
        created = []
        monkeypatch.setattr('bin.logic_tools.excel_exporter',
                            lambda filename: created.append(FakeExcelExporter(filename)) or created[-1])
        return created

    def test_writes_a_worksheet_per_approval_state(self, exporter):
        db = FakeDatabase(approved=[make_text_link('TIC-401')],
                          unapproved=[make_text_link('FIT-205')],
                          rejected=[make_text_link('PIT-100')])

        export_text_excel_with_data(never_stop, DOCUMENT, 'out.xlsx', db)

        workbook = exporter[0]
        assert list(workbook.headers) == WORKSHEET_NAMES
        assert workbook.row_values('Approved Links', 1)[0] == 'TIC-401'
        assert workbook.row_values('Unapproved Links', 1)[0] == 'FIT-205'
        assert workbook.row_values('Rejected Links', 1)[0] == 'PIT-100'
        assert workbook.closed

    def test_empty_document_still_produces_the_worksheets(self, exporter):
        reported = []

        def record(textbox_entry, label_text, percentage):
            reported.append(percentage)
            return False

        export_text_excel_with_data(record, DOCUMENT, 'out.xlsx', FakeDatabase())

        assert list(exporter[0].headers) == WORKSHEET_NAMES
        assert reported == [100.0]

    def test_stop_signal_aborts_without_writing_further_links(self, exporter):
        db = FakeDatabase(approved=[make_text_link('TIC-401'), make_text_link('TIC-402')],
                          unapproved=[make_text_link('FIT-205')])

        export_text_excel_with_data(lambda *_: True, DOCUMENT, 'out.xlsx', db)

        workbook = exporter[0]
        assert len(workbook.rows['Approved Links']) == 1
        assert workbook.rows['Unapproved Links'] == {}
        assert workbook.closed


class TestDocumentScopedTextLinkQueries:
    @pytest.fixture
    def db(self, tmp_project_root):
        database = Database('P')
        yield database
        database.close_db()

    def test_each_query_only_returns_links_for_that_document(self, db):
        db.save_approved_text_link(make_text_link('TIC-401'))
        db.save_approved_text_link(make_text_link('TIC-402', path='projects/P/texts/other.pdf'))
        db.save_unapproved_text_link(make_text_link('FIT-205'))
        db.save_rejected_text_link(make_text_link('PIT-100'))

        approved = db.get_all_approved_text_links_by_document(DOCUMENT)
        unapproved = db.get_all_unapproved_text_links_by_document(DOCUMENT)
        rejected = db.get_all_rejected_text_links_by_document(DOCUMENT)

        assert [link['id'] for link in approved] == ['TIC-401']
        assert [link['id'] for link in unapproved] == ['FIT-205']
        assert [link['id'] for link in rejected] == ['PIT-100']

    def test_unknown_document_returns_empty_lists(self, db):
        db.save_approved_text_link(make_text_link('TIC-401'))

        assert db.get_all_approved_text_links_by_document('projects/P/texts/missing.pdf') == []
        assert db.get_all_unapproved_text_links_by_document('projects/P/texts/missing.pdf') == []
        assert db.get_all_rejected_text_links_by_document('projects/P/texts/missing.pdf') == []
