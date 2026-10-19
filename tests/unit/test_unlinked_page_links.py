"""Unlinked page links must still reach ACM, and therefore the built HMI display.

A page link whose drawing text matched no HMI display is stored under
``unlinked_page_links``. It used to be skipped when the display was built, so it never
existed as an ACM object and could not appear on the canvas or in the exported display.
"""

import xml.etree.ElementTree as ET

import pytest

from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_gfx_file_editor import ElementMapItem, GfxFileEditor
from bin.logic_hmi_display import HMI_Display, acm_safe_token
from bin.logic_validators import Validators


PAGE_LINK_SYMBOL_XML = (
    '<group name="{ObjectName}_PageLink" visible="true">'
    '<text name="{ObjectName}_Label" caption="{Label}" />'
    '<animations>'
    '<animateTouch TouchStyle="rectangular" pressAction="" repeatAction="" '
    'releaseAction="Display &quot;{NavToDisplayName}&quot;" repeatRate="0.25" />'
    '</animations>'
    '</group>'
)


def make_page_link(pno=0, path='drawing.pdf', **overrides):
    page_link = {
        'path': path,
        'pno': pno,
        'roi_uid': f'{pno}-100-100-200-200-hmi_page_link',
        'minX': 100,
        'minY': 200,
        'maxX': 300,
        'maxY': 400,
        'page_width': 1000,
        'page_height': 500,
        'flip': 0,
    }
    page_link.update(overrides)
    return page_link


class RecordingAcmDataHandler:
    def __init__(self):
        self.calls = []

    def create_new_hmi_page_link_in_acm(self, display_name, page_link_id, factory_talk_view_se_id,
                                        navigate_to_display_name, center_point, orientation,
                                        label=None, name_token=None):
        self.calls.append({
            'display_name': display_name,
            'page_link_id': page_link_id,
            'navigate_to_display_name': navigate_to_display_name,
            'center_point': center_point,
            'orientation': orientation,
            'label': label,
            'name_token': name_token,
        })


class FakeInternalDatabase:
    def __init__(self, displays):
        self.__displays = displays

    def get_all_hmi_displays(self):
        return self.__displays


def make_display_for_build(displays, name='Area_P1', path='drawing.pdf', pno=0):
    """Build an HMI_Display without running __init__, which builds Tk backed views."""
    display = HMI_Display.__new__(HMI_Display)
    display.name = name
    display._HMI_Display__db = FakeInternalDatabase(displays)
    display._HMI_Display__path = path
    display._HMI_Display__pno = pno
    display._HMI_Display__flow_direction = 0
    display._HMI_Display__acm_data_handler = RecordingAcmDataHandler()
    return display


def create_page_links_in_acm(display, width=1000, height=500):
    display._HMI_Display__create_page_links_in_acm('ft_view_se_id', width, height)
    return display._HMI_Display__acm_data_handler.calls


class TestAcmSafeToken:
    @pytest.mark.parametrize('text', ['SHEET 5', 'P-101', '55/TI-00143', '  ', 'Area__One_'])
    def test_token_is_an_acm_valid_name(self, text):
        assert Validators.check_object_name_acm_valid(acm_safe_token(text))

    def test_separators_collapse_to_single_underscores(self):
        assert acm_safe_token('TI/00143 - Sheet') == 'TI_00143_Sheet'

    def test_leading_digit_is_prefixed(self):
        assert acm_safe_token('101 Sheet').startswith('D_')

    def test_empty_text_falls_back(self):
        assert acm_safe_token('') == 'Unlinked'
        assert acm_safe_token(None) == 'Unlinked'


class TestCreatePageLinksInAcm:
    def test_linked_page_link_navigates_to_the_owning_display(self):
        displays = [{'name': 'Tank_Farm', 'page_links': [make_page_link()]}]
        display = make_display_for_build(displays)

        calls = create_page_links_in_acm(display)

        assert len(calls) == 1
        assert calls[0]['navigate_to_display_name'] == 'Tank_Farm'
        assert calls[0]['label'] is None
        assert calls[0]['name_token'] is None
        # Centre of the ROI scaled from the page size to the display size.
        assert calls[0]['center_point'] == (200, 300)

    def test_unlinked_page_link_is_created_without_a_target(self):
        displays = [{'name': 'Area_P1',
                     'unlinked_page_links': [make_page_link(page_name='SHEET 5')]}]
        display = make_display_for_build(displays)

        calls = create_page_links_in_acm(display)

        assert len(calls) == 1
        assert calls[0]['navigate_to_display_name'] == ''
        assert calls[0]['label'] == 'SHEET 5 (?)'
        assert calls[0]['name_token'] == 'SHEET_5'
        assert calls[0]['center_point'] == (200, 300)

    def test_linked_and_unlinked_page_links_are_both_created(self):
        displays = [
            {'name': 'Tank_Farm', 'page_links': [make_page_link()]},
            {'name': 'Area_P1', 'unlinked_page_links': [make_page_link(page_name='SHEET 5')]},
        ]
        display = make_display_for_build(displays)

        calls = create_page_links_in_acm(display)

        assert [call['navigate_to_display_name'] for call in calls] == ['Tank_Farm', '']

    def test_unlinked_page_link_on_another_page_is_skipped(self):
        displays = [{'name': 'Area_P2',
                     'unlinked_page_links': [make_page_link(pno=1, page_name='SHEET 5')]}]
        display = make_display_for_build(displays, pno=0)

        assert create_page_links_in_acm(display) == []

    def test_unlinked_page_link_in_another_document_is_skipped(self):
        displays = [{'name': 'Other_P1',
                     'unlinked_page_links': [make_page_link(path='other.pdf', page_name='SHEET 5')]}]
        display = make_display_for_build(displays, path='drawing.pdf')

        assert create_page_links_in_acm(display) == []

    def test_display_without_any_page_link_keys_is_skipped(self):
        display = make_display_for_build([{'name': 'Empty'}])

        assert create_page_links_in_acm(display) == []

    def test_page_link_without_a_page_name_still_yields_a_valid_object_name(self):
        displays = [{'name': 'Area_P1', 'unlinked_page_links': [make_page_link()]}]
        display = make_display_for_build(displays)

        calls = create_page_links_in_acm(display)

        assert Validators.check_object_name_acm_valid(calls[0]['name_token'])


class TestCreateNewHmiPageLinkInAcm:
    @pytest.fixture
    def handler(self, monkeypatch):
        """An ACM_Data_Handler that records the SQL instead of connecting to SQL Server."""
        executed = []

        class FakeCursor:
            def execute(self, sql):
                executed.append(sql)

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

        def fake_db_connector(connection_string):
            def decorator(func):
                return lambda: func(FakeConnection())
            return decorator

        monkeypatch.setattr('bin.logic_acm_data_handler.db_connector', fake_db_connector)
        monkeypatch.setattr('bin.logic_acm_data_handler.os.getlogin', lambda: 'tester')

        handler = ACM_Data_Handler.__new__(ACM_Data_Handler)
        handler._ACM_Data_Handler__connection_string = 'unused'
        handler._ACM_Data_Handler__project_id = 1
        handler._ACM_Data_Handler__controller_id = 2
        handler._ACM_Data_Handler__controller_object_id = 3
        handler.executed = executed
        return handler

    def test_linked_page_link_keeps_the_existing_name_and_label(self, handler):
        handler.create_new_hmi_page_link_in_acm('Area_P1', 'roi-1', 10, 'Tank_Farm', (100, 200), 0)

        sql = handler.executed[0]
        assert "'Area_P1_to_Tank_Farm_100_200'" in sql
        assert "'Label','String','Tank Farm'" in sql
        assert "'NavToDisplayName','String','Tank_Farm'" in sql

    def test_unlinked_page_link_uses_the_token_and_has_no_target(self, handler):
        handler.create_new_hmi_page_link_in_acm('Area_P1', 'roi-1', 10, '', (100, 200), 0,
                                                label='SHEET 5 (?)', name_token='SHEET_5')

        sql = handler.executed[0]
        assert "'Area_P1_to_SHEET_5_100_200'" in sql
        assert "'Label','String','SHEET 5 (?)'" in sql
        assert "'NavToDisplayName','String',''" in sql

    def test_apostrophes_in_the_label_are_escaped(self, handler):
        handler.create_new_hmi_page_link_in_acm('Area_P1', 'roi-1', 10, '', (100, 200), 0,
                                                label="OPERATOR'S SHEET", name_token='Sheet')

        assert "'Label','String','OPERATOR''S SHEET'" in handler.executed[0]


class TestPageLinkButtonIsInert:
    def make_editor(self, nav_to_display_name):
        editor = GfxFileEditor.__new__(GfxFileEditor)
        editor.project_name = 'project'
        editor.acm_data_handler = None
        editor.library_parsers = {}
        editor.element_map = {
            'PL1': ElementMapItem(catalog_number='PageLink', object_id=1, controller_id=2,
                                  xml_element=None, library_id='lib', Cfg_PositionX=0,
                                  Cfg_PositionY=0, isPositioned=True)
        }

        values = {'Label': 'SHEET 5 (?)', 'NavToDisplayName': nav_to_display_name}
        # Patch the bound module function the method resolves at call time.
        import bin.logic_gfx_file_editor as module
        self._original = module.process_acm_variable
        module.process_acm_variable = lambda variable, *args, **kwargs: values.get(variable)
        return editor, module

    def resolve(self, nav_to_display_name):
        editor, module = self.make_editor(nav_to_display_name)
        try:
            editor.get_object_xml_symbol('PL1', PAGE_LINK_SYMBOL_XML)
        finally:
            module.process_acm_variable = self._original
        return editor.element_map['PL1'].xml_element

    def test_page_link_without_a_target_gets_no_touch_animation(self):
        root = self.resolve('')

        assert root.find('.//animateTouch') is None
        assert root.find('.//animations') is None

    def test_page_link_without_a_target_leaks_no_placeholder(self):
        assert '{' not in ET.tostring(self.resolve(''), encoding='unicode')

    def test_page_link_with_a_target_keeps_navigating(self):
        touch = self.resolve('Tank_Farm').find('.//animateTouch')

        assert touch.get('releaseAction') == 'Display "Tank_Farm"'
