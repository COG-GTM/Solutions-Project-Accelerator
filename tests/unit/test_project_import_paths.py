"""Path-traversal and zip-bomb guards for .aip project import (bin/logic_export_import_project.py)."""

import configparser
import io
import os
import zipfile

import pytest

from bin import logic_export_import_project as aip
from bin.logic_project_paths import InvalidProjectName, find_existing_project, is_valid_project_name, project_dir


def make_aip(path, name, extra_files=None):
    ini = configparser.ConfigParser()
    ini['DEFAULT']['Name'] = name
    ini['DEFAULT']['Description'] = 'd'
    ini['DEFAULT']['Version'] = '1.0'
    buffer = io.StringIO()
    ini.write(buffer)
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('project.ini', buffer.getvalue())
        zf.writestr('drawings/a/0.png', b'png')
        for member, data in (extra_files or {}).items():
            zf.writestr(member, data)
    return str(path)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    app = tmp_path / 'app'
    (app / 'projects').mkdir(parents=True)
    monkeypatch.chdir(app)
    return tmp_path


def files_outside_projects(root):
    projects = os.path.join(root, 'app', 'projects')
    found = []
    for folder, _, names in os.walk(root):
        for name in names:
            full = os.path.join(folder, name)
            if not full.startswith(projects + os.sep) and not name.endswith('.aip'):
                found.append(full)
    return found


@pytest.mark.parametrize('name', [
    'Pump Skid', 'Line_3', 'plant-2024 (rev.2)', 'Projekt Kühlung', 'A' * 100,
])
def test_accepts_plain_project_names(name):
    assert is_valid_project_name(name)


@pytest.mark.parametrize('name', [
    '', '.', '..', '../x', '..\\x', 'a/b', 'a\\b', 'C:evil', 'C:\\Users\\Public',
    '/etc', '\\\\server\\share', '..\\..\\..\\Users\\Public\\spa_traversal_test',
    'trailing.', 'trailing ', ' leading', '.hidden', 'CON', 'nul.txt', 'A' * 101, 'tab\tname', None,
])
def test_rejects_unsafe_project_names(name):
    assert not is_valid_project_name(name)
    with pytest.raises(InvalidProjectName):
        project_dir(name)


def test_project_dir_is_direct_child_of_projects(workspace):
    assert project_dir('Pump Skid') == os.path.join(str(workspace), 'app', 'projects', 'Pump Skid')


@pytest.mark.parametrize('name', [
    '..\\..\\..\\Users\\Public\\spa_traversal_test',
    '../../../Users/Public/spa_traversal_test',
    '../escape',
])
def test_traversal_name_in_project_ini_is_rejected_before_writing(workspace, name):
    archive = make_aip(workspace / 'pump_skid.aip', name)

    with pytest.raises(InvalidProjectName):
        aip.read_project_name_from_zip(archive)
    with pytest.raises(InvalidProjectName):
        aip.import_project(archive, name)

    assert files_outside_projects(str(workspace)) == []
    assert os.listdir(workspace / 'app' / 'projects') == []


def test_import_extracts_valid_project(workspace):
    archive = make_aip(workspace / 'ok.aip', 'Pump Skid')

    name = aip.read_project_name_from_zip(archive)
    assert aip.import_project(archive, name) is True

    target = workspace / 'app' / 'projects' / 'Pump Skid'
    assert (target / 'project.ini').is_file()
    assert (target / 'drawings' / 'a' / '0.png').read_bytes() == b'png'


@pytest.mark.parametrize('member', ['../evil.txt', '..\\evil.txt', '/abs.txt', 'C:/evil.txt', 'a/../../evil.txt'])
def test_unsafe_member_names_are_rejected(workspace, member):
    archive = make_aip(workspace / 'bad.aip', 'Pump Skid', {member: b'x'})

    with pytest.raises(aip.InvalidProjectArchive):
        aip.import_project(archive, 'Pump Skid')

    assert not (workspace / 'app' / 'projects' / 'Pump Skid').exists()
    assert files_outside_projects(str(workspace)) == []


def test_entry_count_limit(workspace, monkeypatch):
    monkeypatch.setattr(aip, 'MAX_ARCHIVE_ENTRIES', 2)
    archive = make_aip(workspace / 'many.aip', 'Pump Skid', {'b.txt': b'x'})

    with pytest.raises(aip.InvalidProjectArchive, match='entries'):
        aip.import_project(archive, 'Pump Skid')
    assert not (workspace / 'app' / 'projects' / 'Pump Skid').exists()


def test_uncompressed_size_limit(workspace, monkeypatch):
    monkeypatch.setattr(aip, 'MAX_ARCHIVE_UNCOMPRESSED_BYTES', 1024)
    archive = str(workspace / 'bomb.aip')
    make_aip(archive, 'Pump Skid')
    with zipfile.ZipFile(archive, 'a', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('big.bin', b'\0' * 4096)

    with pytest.raises(aip.InvalidProjectArchive, match='expands'):
        aip.import_project(archive, 'Pump Skid')
    assert not (workspace / 'app' / 'projects' / 'Pump Skid').exists()


def projects_entries(workspace):
    return sorted(os.listdir(workspace / 'app' / 'projects'))


def test_read_project_name_rejects_unsafe_members_before_any_delete(workspace):
    archive = make_aip(workspace / 'bad.aip', 'Pump Skid', {'../bad.txt': b'x'})

    with pytest.raises(aip.InvalidProjectArchive):
        aip.read_project_name_from_zip(archive)


def test_oversized_project_ini_is_rejected_before_reading(workspace, monkeypatch):
    monkeypatch.setattr(aip, 'MAX_PROJECT_INI_BYTES', 16)
    archive = make_aip(workspace / 'big_ini.aip', 'Pump Skid')

    with pytest.raises(aip.InvalidProjectArchive, match='project.ini'):
        aip.read_project_name_from_zip(archive)


def test_existing_project_requires_replace(workspace):
    aip.import_project(make_aip(workspace / 'v1.aip', 'Pump Skid'), 'Pump Skid')

    with pytest.raises(FileExistsError):
        aip.import_project(make_aip(workspace / 'v2.aip', 'Pump Skid'), 'Pump Skid')


def test_replace_swaps_in_new_content(workspace):
    aip.import_project(make_aip(workspace / 'v1.aip', 'Pump Skid', {'old.txt': b'old'}), 'Pump Skid')

    aip.import_project(make_aip(workspace / 'v2.aip', 'Pump Skid', {'new.txt': b'new'}), 'Pump Skid', replace=True)

    target = workspace / 'app' / 'projects' / 'Pump Skid'
    assert (target / 'new.txt').read_bytes() == b'new'
    assert not (target / 'old.txt').exists()
    assert projects_entries(workspace) == ['Pump Skid']


@pytest.mark.parametrize('extra', [{'../bad.txt': b'x'}, {'big.bin': b'\0' * 4096}])
def test_rejected_replacement_keeps_existing_project(workspace, monkeypatch, extra):
    aip.import_project(make_aip(workspace / 'v1.aip', 'Pump Skid', {'old.txt': b'old'}), 'Pump Skid')
    monkeypatch.setattr(aip, 'MAX_ARCHIVE_UNCOMPRESSED_BYTES', 1024)

    with pytest.raises(aip.InvalidProjectArchive):
        aip.import_project(make_aip(workspace / 'v2.aip', 'Pump Skid', extra), 'Pump Skid', replace=True)

    assert (workspace / 'app' / 'projects' / 'Pump Skid' / 'old.txt').read_bytes() == b'old'
    assert projects_entries(workspace) == ['Pump Skid']


def test_failed_extraction_keeps_existing_project_and_cleans_staging(workspace, monkeypatch):
    aip.import_project(make_aip(workspace / 'v1.aip', 'Pump Skid', {'old.txt': b'old'}), 'Pump Skid')

    def boom(self, path=None, members=None, pwd=None):
        open(os.path.join(path, 'partial.txt'), 'w').close()
        raise OSError('disk full')

    monkeypatch.setattr(zipfile.ZipFile, 'extractall', boom)
    with pytest.raises(OSError):
        aip.import_project(make_aip(workspace / 'v2.aip', 'Pump Skid'), 'Pump Skid', replace=True)

    assert (workspace / 'app' / 'projects' / 'Pump Skid' / 'old.txt').read_bytes() == b'old'
    assert projects_entries(workspace) == ['Pump Skid']


def test_symlinked_project_folder_is_rejected(workspace):
    outside = workspace / 'outside'
    outside.mkdir()
    os.symlink(outside, workspace / 'app' / 'projects' / 'Pump Skid', target_is_directory=True)
    archive = make_aip(workspace / 'link.aip', 'Pump Skid')

    with pytest.raises(InvalidProjectName):
        aip.read_project_name_from_zip(archive)
    with pytest.raises(InvalidProjectName):
        aip.import_project(archive, 'Pump Skid', replace=True)

    assert os.listdir(outside) == []


def test_case_only_replacement_replaces_existing_folder(workspace):
    aip.import_project(make_aip(workspace / 'v1.aip', 'Pump', {'old.txt': b'old'}), 'Pump')

    with pytest.raises(FileExistsError):
        aip.import_project(make_aip(workspace / 'v2.aip', 'pump'), 'pump')
    aip.import_project(make_aip(workspace / 'v2.aip', 'pump', {'new.txt': b'new'}), 'pump', replace=True)

    assert projects_entries(workspace) == ['pump']
    assert (workspace / 'app' / 'projects' / 'pump' / 'new.txt').read_bytes() == b'new'


def test_find_existing_project_is_case_insensitive(workspace):
    (workspace / 'app' / 'projects' / 'Pump Skid').mkdir()
    (workspace / 'app' / 'projects' / '.aip-replaced-x').mkdir()

    assert find_existing_project('Pump Skid') == 'Pump Skid'
    assert find_existing_project('PUMP SKID') == 'Pump Skid'
    assert find_existing_project('.aip-replaced-x') is None
    assert find_existing_project('Other') is None


def test_failed_backup_cleanup_is_reported_and_kept(workspace, monkeypatch):
    aip.import_project(make_aip(workspace / 'v1.aip', 'Pump Skid', {'old.txt': b'old'}), 'Pump Skid')

    def deny(path, *args, **kwargs):
        raise PermissionError('read-only')

    monkeypatch.setattr(aip.shutil, 'rmtree', deny)
    with pytest.raises(aip.ReplacedProjectNotRemoved) as excinfo:
        aip.import_project(make_aip(workspace / 'v2.aip', 'Pump Skid', {'new.txt': b'new'}), 'Pump Skid', replace=True)

    projects = workspace / 'app' / 'projects'
    assert (projects / 'Pump Skid' / 'new.txt').read_bytes() == b'new'
    assert os.path.dirname(excinfo.value.backup_path) == str(projects)
    assert (projects / os.path.basename(excinfo.value.backup_path) / 'old.txt').read_bytes() == b'old'
    assert excinfo.value.backup_path in str(excinfo.value)
