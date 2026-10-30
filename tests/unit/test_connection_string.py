"""Unit tests for bin/logic_connection_string.py (SQL password redaction/splitting)."""

import pytest

from bin.logic_connection_string import (add_password, quote_odbc_value,
                                         redact_connection_string, split_password,
                                         uses_sql_login)

BASE = 'DRIVER={ODBC Driver 18 for SQL Server};SERVER=acm01\\SQLEXPRESS;DATABASE=ACM;'


class TestSplitPassword:
    def test_password_in_the_middle_is_removed(self):
        stripped, password = split_password(BASE + 'UID=alice;PWD=s3cret;TrustServerCertificate=yes;')
        assert password == 's3cret'
        assert stripped == BASE + 'UID=alice;TrustServerCertificate=yes;'

    def test_braced_password_with_separators_round_trips(self):
        secret = 'a;b}c{d '
        connection_string = add_password(BASE + 'UID=alice;', secret) + 'TrustServerCertificate=yes;'
        stripped, password = split_password(connection_string)
        assert password == secret
        assert 'PWD' not in stripped
        assert stripped == BASE + 'UID=alice;TrustServerCertificate=yes;'

    @pytest.mark.parametrize('attribute', ['PWD', 'pwd', 'Password'])
    def test_attribute_name_is_case_insensitive(self, attribute):
        stripped, password = split_password(BASE + 'UID=a;' + attribute + '=x')
        assert password == 'x'
        assert stripped == BASE + 'UID=a;'

    def test_windows_authentication_has_no_password(self):
        connection_string = BASE + 'Trusted_Connection=yes;'
        assert split_password(connection_string) == (connection_string, None)

    def test_empty_password(self):
        assert split_password(BASE + 'UID=a;PWD=;') == (BASE + 'UID=a;', '')

    def test_none_is_tolerated(self):
        assert split_password(None) == ('', None)


class TestRedaction:
    def test_password_value_never_appears(self):
        redacted = redact_connection_string(BASE + 'UID=alice;PWD=hunter2;TrustServerCertificate=yes;')
        assert 'hunter2' not in redacted
        assert 'PWD' not in redacted
        assert redacted == BASE + 'UID=alice;TrustServerCertificate=yes;'

    def test_braced_password_is_fully_redacted(self):
        redacted = redact_connection_string(add_password(BASE + 'UID=a;', 'x;y}z') + 'Encrypt=yes;')
        assert redacted == BASE + 'UID=a;Encrypt=yes;'

    def test_string_without_password_is_unchanged(self):
        connection_string = BASE + 'Trusted_Connection=yes;'
        assert redact_connection_string(connection_string) == connection_string


class TestHelpers:
    @pytest.mark.parametrize('value, expected', [
        ('plain', 'plain'), ('a;b', '{a;b}'), ('a}b', '{a}}b}'), (' pad', '{ pad}'), ('', '')])
    def test_quote_odbc_value(self, value, expected):
        assert quote_odbc_value(value) == expected

    def test_uses_sql_login(self):
        assert uses_sql_login(BASE + 'UID=alice;')
        assert not uses_sql_login(BASE + 'Trusted_Connection=yes;')


class TestBuildConnectionStringLogging:
    def test_password_is_quoted_and_not_logged(self, monkeypatch, caplog):
        pytest.importorskip('pyodbc')
        from bin import logic_sql_database

        monkeypatch.setattr(logic_sql_database.pyodbc, 'drivers',
                            lambda: ['ODBC Driver 18 for SQL Server'], raising=False)
        with caplog.at_level('INFO'):
            connection_string = logic_sql_database.build_connection_string(
                'acm01', 'ACM', user='alice', password='p;w}d', use_windows_authentication=False)

        assert split_password(connection_string)[1] == 'p;w}d'
        assert 'p;w}d' not in caplog.text and 'PWD' not in caplog.text
        assert 'acm01' in caplog.text
