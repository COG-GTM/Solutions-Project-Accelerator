"""ACM SQL Server access must bind every value instead of formatting it into the SQL text.

Project IDs, parameter text, sub-object descriptions, library filters and name templates can come
from an imported .aip archive or from OCR/LLM output, so they must never become executable SQL.
"""

import re

import pandas as pd
import pytest

import bin.logic_acm_data_handler as handler_module
import bin.logic_acm_db_commands as commands
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_acm_db_commands import bind_params, parameterize_acm_filter, render_name_template, to_db_id


INJECTED_PROJECT_ID = '1; SELECT 1/0; --'


class FakeCursor:
    def __init__(self, calls):
        self.calls = calls

    def execute(self, sql, *params):
        self.calls.append((sql, params[0] if params else None))


class FakeConnection:
    def __init__(self, calls):
        self.calls = calls

    def cursor(self):
        return FakeCursor(self.calls)


@pytest.fixture
def executed(monkeypatch):
    calls = []

    def fake_db_connector(_connection_string):
        def decorator(func):
            def wrapper(*args, **kwargs):
                return func(FakeConnection(calls), *args, **kwargs)
            return wrapper
        return decorator

    monkeypatch.setattr(handler_module, 'db_connector', fake_db_connector)
    monkeypatch.setattr(handler_module.os, 'getlogin', lambda: 'engineer')
    return calls


@pytest.fixture
def queries(monkeypatch):
    calls = []

    def fake_read_sql_query(sql, con, params=None, index_col=None, **kwargs):
        calls.append((sql, params))
        if sql.startswith('SELECT COUNT(*)'):
            return pd.DataFrame([[1]])
        return pd.DataFrame({'Name': []})

    monkeypatch.setattr(handler_module.pd, 'read_sql_query', fake_read_sql_query)
    return calls


@pytest.fixture
def handler():
    handler = object.__new__(ACM_Data_Handler)
    handler._ACM_Data_Handler__connection_string = 'DRIVER=fake'
    handler._ACM_Data_Handler__engine = object()
    handler._ACM_Data_Handler__project_id = None
    handler._ACM_Data_Handler__is_linked = False
    handler._ACM_Data_Handler__project_missing_callback = None
    return handler


def assert_bound(sql, params, *values):
    assert sql.count('?') == len(params)
    for value in values:
        assert str(value) not in sql
        assert value in params


@pytest.mark.parametrize('value', [INJECTED_PROJECT_ID, "1 OR 1=1", '', 'abc', -1, 1.5, True, None, [1]])
def test_to_db_id_rejects_non_integer_ids(value):
    with pytest.raises(ValueError):
        to_db_id(value)


@pytest.mark.parametrize('value, expected', [(6044, 6044), ('6044', 6044), (' 9 ', 9), (9.0, 9), ('9.0', 9)])
def test_to_db_id_accepts_integer_ids(value, expected):
    assert to_db_id(value) == expected


def test_injected_project_id_is_rejected_before_any_query(handler, queries, monkeypatch):
    missing = []
    handler._ACM_Data_Handler__project_missing_callback = lambda: missing.append(True)
    monkeypatch.setattr(handler, 'set_objects_filter', lambda *a, **k: pytest.fail('must not query ACM'))

    handler.set_project_id(INJECTED_PROJECT_ID)

    assert handler.get_project_id() is None
    assert queries == []
    assert missing == [True]


def test_invalid_project_id_unlinks_previous_project(handler, queries, monkeypatch):
    monkeypatch.setattr(handler, 'set_objects_filter', lambda *a, **k: None)
    handler.set_project_id(10)
    assert handler.get_project_id() == 10

    handler.set_project_id(INJECTED_PROJECT_ID)

    assert handler.get_project_id() is None
    assert handler._ACM_Data_Handler__is_linked is False


@pytest.mark.parametrize('acm_filter', [
    "Objects.ProjectID=1",
    "SubObjects.ChangeUser='sa'",
    "RegisteredLibraries.Password='x'",
    "Projects.Name='x'",
])
def test_filter_columns_outside_allowlist_are_rejected(acm_filter):
    with pytest.raises(ValueError):
        parameterize_acm_filter(acm_filter)


def test_filter_columns_are_canonicalised():
    sql, params = parameterize_acm_filter("registeredlibraries.librarytype='HMI'")
    assert sql == 'and (RegisteredLibraries.LibraryType = ?)'
    assert params == ('HMI',)


def test_valid_project_id_is_cast_and_bound(handler, queries, monkeypatch):
    monkeypatch.setattr(handler, 'set_objects_filter', lambda *a, **k: None)
    handler.set_project_id('6044')
    assert handler.get_project_id() == 6044

    handler.check_if_project_exists()
    sql, params = queries[-1]
    assert sql == 'SELECT COUNT(*) FROM Projects WHERE ProjectID=?'
    assert params == (6044,)


def test_parameter_value_with_quote_is_written_literally(handler, executed):
    handler.write_parameter_value("O'Brien", 42, 'Description')

    sql, params = executed[-1]
    assert_bound(sql, params, "O'Brien", 'Description')
    assert params == ("O'Brien", 1, '', 42, 'Description')


def test_subparameter_value_with_sql_payload_is_bound(handler, executed):
    payload = "x'; DROP TABLE Projects; --"
    handler.write_subparameter_value(payload, '7', 'Tag')

    sql, params = executed[-1]
    assert_bound(sql, params, payload)
    assert params == (payload, 1, '', 7, 'Tag')


def test_subobject_description_is_bound(handler, executed):
    payload = "Tank'; DELETE FROM Projects; --"
    handler.set_subobject_description(5, payload)

    sql, params = executed[-1]
    assert sql == 'UPDATE SubObjects SET Description=? WHERE SubObjectID=?'
    assert params == (payload, 5)


@pytest.mark.parametrize('method, args', [
    ('write_parameter_value', ('v', INJECTED_PROJECT_ID, 'p')),
    ('write_subparameter_value', ('v', INJECTED_PROJECT_ID, 'p')),
    ('set_subobject_description', (INJECTED_PROJECT_ID, 'd')),
    ('delete_subobject', (INJECTED_PROJECT_ID,)),
])
def test_writes_reject_injected_ids(handler, executed, method, args):
    with pytest.raises(ValueError):
        getattr(handler, method)(*args)
    assert executed == []


def test_create_subobject_binds_library_values(handler, executed, monkeypatch):
    monkeypatch.setattr(handler, 'get_reference_type_number', lambda _type: 1)
    parameters = {
        'Index': {'RType': 'Immediate', 'AInc': 'false', 'DVal': "1'; DROP TABLE Objects; --", 'DType': 'String', 'ParH': "It's help"},
        'Label': {'RType': 'Immediate', 'AInc': 'false', 'DVal': "O'Brien", 'DType': 'String', 'ParH': ''},
    }

    name = handler.create_subobject(3, {'Name': 'Step_{Label}', 'Type': 'Step'}, parameters)

    assert name == "Step_O'Brien"
    sql, params = executed[-1]
    assert_bound(sql, params, "O'Brien", "1'; DROP TABLE Objects; --", "It's help", "Step_O'Brien")
    assert params[1] == 3


@pytest.mark.parametrize('template', ['{Index.__class__}', '{Index[0]}', '{Index!r}', '{Missing}', '{0}'])
def test_name_templates_only_allow_plain_fields(template):
    with pytest.raises(ValueError):
        render_name_template(template, {'Index': '01'})


def test_library_filter_is_parameterized(handler, queries):
    handler._ACM_Data_Handler__project_id = 6044
    handler.get_all_objects_with_acm_filter(
        "RegisteredLibraries.LibraryType='HMI' And RegisteredLibraries.Category='Display'")

    sql, params = queries[-1]
    assert "'HMI'" not in sql and "'Display'" not in sql
    assert 'and (RegisteredLibraries.LibraryType = ? AND RegisteredLibraries.Category = ?)' in sql
    assert params == (6044, 'HMI', 'Display')


@pytest.mark.parametrize('method', ['get_all_objects_with_acm_filter', 'get_all_subobjects_with_acm_filter'])
@pytest.mark.parametrize('acm_filter', [
    "RegisteredLibraries.LibraryType='HMI'; DROP TABLE Projects; --",
    "RegisteredLibraries.LibraryType='HMI' OR 1=1",
    "1=1",
    "Projects.Name='x'",
    "RegisteredLibraries.Name=(SELECT TOP 1 Name FROM Projects)",
])
def test_unsupported_library_filters_are_rejected(handler, queries, method, acm_filter):
    handler._ACM_Data_Handler__project_id = 6044
    result = getattr(handler, method)(acm_filter)
    assert result.empty
    assert queries == []


def test_filter_literals_are_unescaped_into_params():
    assert parameterize_acm_filter("Objects.Name LIKE 'O''Brien%' or SubObjects.Name<>'x'") == (
        'and (Objects.Name LIKE ? OR SubObjects.Name <> ?)', ("O'Brien%", 'x'))
    assert parameterize_acm_filter('') == ('', ())


@pytest.mark.parametrize('method, args', [
    ('get_registered_library', ("x' OR '1'='1",)),
    ('get_raw_object', (11,)),
    ('get_all_subobjects_in_object', (11, "Step' OR '1'='1")),
    ('get_subobject_in_object_with_name', (11, "O'Brien", 'Step')),
    ('get_all_parameters_in_object', (11, "Name' --")),
    ('get_parameter_in_object', (11, "O'Brien")),
    ('get_all_subparameters_in_subobject', (12, "O'Brien")),
    ('get_object_id_by_spa_id', ("spa'--",)),
    ('get_reference_type_number', ("Immediate'--",)),
    ('get_subobject_description', (12,)),
    ('get_display_objects', ("Main'--", 13)),
    ('get_display', ("Main'--", 13)),
    ('get_all_displays', (13,)),
])
def test_reads_bind_all_values(handler, queries, method, args):
    try:
        getattr(handler, method)(*args)
    except (KeyError, IndexError, AttributeError, TypeError):
        pass  # empty fake frames; only the issued SQL matters here
    assert queries, method
    sql, params = queries[-1]
    assert sql.count('?') == len(params)
    for arg in args:
        if isinstance(arg, str):
            assert arg not in sql
            assert arg in params


def test_templates_have_one_param_name_per_placeholder():
    templates = [name for name in dir(commands) if name + '_params' in dir(commands)]
    assert len(templates) >= 20
    for name in templates:
        sql = getattr(commands, name)
        param_names = getattr(commands, name + '_params')
        assert sql.count('?') == len(param_names), name
        assert not re.search(r'\{(?!filter\}|subparameter_values\})\w*\}', sql), name


def test_bind_params_casts_ids_and_stringifies_values():
    assert bind_params(('object_id', 'value', 'ref_type'), object_id='5', value=3.5, ref_type='1') == (5, '3.5', 1)
    with pytest.raises(ValueError):
        bind_params(('object_id',), object_id=INJECTED_PROJECT_ID)
