"""Names written into ACM console scripts (.tp) and InstanceData XML must not inject commands.

Project names can come from an imported .aip archive and control module names from OCR'd
drawings, so a double quote or line break in either must be refused before ACMConsole.exe
runs, and every XML attribute must be escaped.
"""

import configparser
import io
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd
import pytest

from bin import logic_acm_console
from bin.logic_acm_console import (
    ACM_Console,
    acm_identifier,
    acm_script_argument,
    render_acm_command,
    render_objects_xml,
    xml_attr,
)
from bin.logic_export_import_project import read_project_name_from_zip


INJECTED_PROJECT = 'Plant" "x.xml"\nCREATEPROJECT "x" "y'
INJECTED_OBJECT = 'A"/><IObj Name="B'
LIBRARY = ['(RA-LIB) Process 5', 'PAI', '5', '1']


class FakeConfig:
    def get_acm_batch_create_enabled(self):
        return True

    def get_acm_controller(self):
        return ['(RA-LIB) Process 5', 'Controller_L8x', '5', '0']

    def get_acm_controller_program(self):
        return 'MainProgram'

    def get_acm_controller_task(self):
        return 'MainTask'

    def get_acm_controller_software_revision(self):
        return None


class FakeDataHandler:
    def __init__(self, controller_name='Plant_controller', project_name=''):
        self.controller_name = controller_name
        self.project_name = project_name

    def get_project_name(self):
        return self.project_name

    def get_controller_name(self):
        return self.controller_name

    def get_all_objects_in_project(self):
        return pd.DataFrame()


class FakeDb:
    def __init__(self, names):
        self.names = names

    def get_all_control_modules(self):
        return [{'id': str(i), 'name': name, 'type': 'PAI'} for i, name in enumerate(self.names)]

    def get_all_object_assignment_regexs(self):
        return [{'regex': '.*', 'library': ['PAI'] + LIBRARY}]


@pytest.fixture
def acm_tmp(tmp_path, monkeypatch):
    """Send every ACM temp file to tmp_path and record scripts instead of running ACMConsole.exe."""
    monkeypatch.setattr(logic_acm_console.tempfile, 'tempdir', str(tmp_path))
    executed = []
    monkeypatch.setattr(ACM_Console, 'execute_with_log_monitoring',
                        lambda self, script, log, progress_callback=None: executed.append(script))
    return tmp_path, executed


def _written(tmp_path, suffix):
    return [p.read_text() for p in tmp_path.iterdir() if p.suffix == suffix]


class TestHelpers:
    @pytest.mark.parametrize('value', ['Plant', 'My Project.v2', r'C:\Users\alice\out', ''])
    def test_script_argument_accepts_plain_text(self, value):
        assert acm_script_argument(value) == value

    @pytest.mark.parametrize('value', [INJECTED_PROJECT, 'a"b', 'a\nb', 'a\rb', 'a\u2028b', 'a\x00b'])
    def test_script_argument_rejects_quote_and_line_breaks(self, value):
        with pytest.raises(ValueError):
            acm_script_argument(value, 'Project name')

    @pytest.mark.parametrize('value', [INJECTED_OBJECT, '1TIC', 'TIC-101', 'TIC 101', '', None])
    def test_identifier_rejects_non_acm_names(self, value):
        with pytest.raises(ValueError):
            acm_identifier(value, 'Controller name')

    def test_render_acm_command_rejects_injected_project_name(self):
        with pytest.raises(ValueError):
            render_acm_command(logic_acm_console.create_project_batch_command,
                               project_name=INJECTED_PROJECT, extended_script_path='x.xml')

    def test_render_acm_command_rejects_injected_controller_name(self):
        with pytest.raises(ValueError):
            render_acm_command(logic_acm_console.build_plc_acm_command, project_name='Plant',
                               controller_name='C" "D', output_path='out')

    def test_render_acm_command_keeps_valid_command(self):
        script = render_acm_command(logic_acm_console.create_controller_batch_command,
                                    project_name='My Plant', controller_name='My_Plant_controller',
                                    extended_script_path=r'C:\Temp\tmp1.xml')
        assert script == '\tCREATECONTROLLER "My Plant" "My_Plant_controller" "C:\\Temp\\tmp1.xml"'

    def test_xml_attr_escapes_markup_and_line_breaks(self):
        assert xml_attr('a"<b>&\'\n') == 'a&quot;&lt;b&gt;&amp;&apos;&#10;'

    def test_render_objects_xml_rejects_injected_object_name(self):
        with pytest.raises(ValueError, match='IObj'):
            render_objects_xml({INJECTED_OBJECT: {'task': 'T', 'program': 'P', 'description': ''}}, *LIBRARY)

    def test_render_objects_xml_escapes_every_attribute(self):
        xml = render_objects_xml({'TIC_101': {'task': 'T"/><IObj Name="X', 'program': 'P',
                                              'description': 'Feed <pump> "A" & B'}}, *LIBRARY)
        objs = ET.fromstring(xml).findall('./IObjs/IObj')
        assert [o.get('Name') for o in objs] == ['TIC_101']
        assert objs[0].get('Description') == 'Feed <pump> "A" & B'
        assert objs[0].get('Task') == 'T"/><IObj Name="X'
        assert objs[0].get('Sol') == '(RA-LIB) Process 5'


class TestAcmConsoleFlows:
    def test_create_project_refuses_injected_project_name(self, acm_tmp):
        tmp_path, executed = acm_tmp
        console = ACM_Console(INJECTED_PROJECT, FakeDataHandler(), FakeDb([]), FakeConfig())

        with pytest.raises(ValueError):
            console.create_acm_project(None, *LIBRARY)

        assert executed == []
        assert not any('CREATEPROJECT "x"' in text for text in _written(tmp_path, '.tp'))

    def test_create_objects_refuses_injected_object_name(self, acm_tmp):
        tmp_path, executed = acm_tmp
        console = ACM_Console('Plant', FakeDataHandler(), FakeDb(['TIC_101', INJECTED_OBJECT]), FakeConfig())

        with pytest.raises(ValueError, match='IObj'):
            console.create_assigned_acm_objects(None)

        assert executed == []
        assert _written(tmp_path, '.tp') == []
        assert _written(tmp_path, '.xml') == []

    def test_create_objects_refuses_injected_controller_name(self, acm_tmp):
        tmp_path, executed = acm_tmp
        handler = FakeDataHandler(controller_name='C" "x.xml"\nGENERATECONTROLLER "P" "C')
        console = ACM_Console('Plant', handler, FakeDb(['TIC_101']), FakeConfig())

        with pytest.raises(ValueError):
            console.create_assigned_acm_objects(None)

        assert executed == []
        assert _written(tmp_path, '.tp') == []

    def test_create_objects_writes_one_command_and_parsable_xml(self, acm_tmp):
        tmp_path, executed = acm_tmp
        console = ACM_Console('Plant', FakeDataHandler(), FakeDb(['TIC_101', 'FIT_102']), FakeConfig())

        console.create_assigned_acm_objects(None)

        assert len(executed) == 1
        with open(executed[0]) as f:
            commands = [line.strip() for line in f if line.strip()]
        assert commands[0] == 'BEGINCREATE' and commands[-1] == 'ENDCREATE'
        assert len(commands) == 3 and commands[1].startswith('CREATEOBJECTS "Plant" "Plant_controller" "')

        xml_path = commands[1].split('"')[5]
        with open(xml_path) as f:
            objs = ET.fromstring(f.read()).findall('./IObjs/IObj')
        assert sorted(o.get('Name') for o in objs) == ['FIT_102', 'TIC_101']

    def test_build_plc_refuses_injected_output_path(self, acm_tmp):
        _, executed = acm_tmp
        console = ACM_Console('Plant', FakeDataHandler(), FakeDb([]), FakeConfig())

        with pytest.raises(ValueError):
            console.build_plc('C:\\out" "x"\nCREATEPROJECT "x', controller_name='Plant_controller')

        assert executed == []


def _aip(tmp_path, name):
    config = configparser.ConfigParser()
    config['DEFAULT'] = {'Name': name}
    buffer = io.StringIO()
    config.write(buffer)
    path = tmp_path / 'project.aip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('project.ini', buffer.getvalue())
    return str(path)


class TestImportedProjectName:
    @pytest.mark.parametrize('name', ['Plant', 'My Project', 'project.v2', 'Project_1'])
    def test_accepts_valid_project_names(self, tmp_path, name):
        assert read_project_name_from_zip(_aip(tmp_path, name)) == name

    @pytest.mark.parametrize('name', ['Plant"\n CREATEPROJECT "x" "y"', 'Plant" "y', '..', '../evil', 'a/b'])
    def test_rejects_unsafe_project_names(self, tmp_path, name):
        with pytest.raises(ValueError):
            read_project_name_from_zip(_aip(tmp_path, name))
