"""ACM SQL Server connections must validate the server's TLS certificate by default."""

import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def sql(monkeypatch):
    connects = []

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, query):
            pass

        def fetchall(self):
            return [types.SimpleNamespace(name="ACM")]

    class _Connection:
        def cursor(self):
            return _Cursor()

    fake_pyodbc = types.ModuleType("pyodbc")
    fake_pyodbc.drivers = lambda: ["ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server"]
    fake_pyodbc.connect = lambda connection_string, **kw: (connects.append(connection_string), _Connection())[1]
    monkeypatch.setitem(sys.modules, "pyodbc", fake_pyodbc)
    monkeypatch.delitem(sys.modules, "bin.logic_sql_database", raising=False)

    import bin.logic_sql_database as module
    module.connects = connects
    return module


def test_build_connection_string_validates_certificate_by_default(sql):
    cs = sql.build_connection_string("acm01\\SQLACM", "ACM", user="eng", password="pw",
                                     use_windows_authentication=False)
    assert "Encrypt=yes;" in cs
    assert "TrustServerCertificate=no;" in cs
    assert not sql.trusts_server_certificate(cs)


def test_build_connection_string_trusts_certificate_only_when_opted_in(sql):
    cs = sql.build_connection_string("acm01\\SQLACM", "ACM", trust_server_certificate=True)
    assert cs.startswith("DRIVER={ODBC Driver 18 for SQL Server};SERVER=acm01\\SQLACM;DATABASE=ACM;Trusted_Connection=yes;")
    assert cs.endswith("Encrypt=yes;TrustServerCertificate=yes;")
    assert sql.trusts_server_certificate(cs)


def test_get_all_databases_validates_certificate_by_default(sql):
    assert sql.get_all_databases("acm01\\SQLACM") == ["ACM"]
    assert sql.connects[-1].endswith("Encrypt=yes;TrustServerCertificate=no;")

    sql.get_all_databases("acm01\\SQLACM", trust_server_certificate=True)
    assert sql.connects[-1].endswith("Encrypt=yes;TrustServerCertificate=yes;")


@pytest.mark.parametrize("cs, expected", [
    ("DRIVER={x};SERVER=s;TrustServerCertificate=yes;", True),
    ("DRIVER={x};SERVER=s; trustservercertificate = True ;", True),
    ("DRIVER={x};SERVER=s;Encrypt=yes;TrustServerCertificate=no;", False),
    ("DRIVER={x};SERVER=s;", False),
    ("", False),
    (None, False),
])
def test_trusts_server_certificate(sql, cs, expected):
    assert sql.trusts_server_certificate(cs) is expected


def test_connection_dialog_does_not_force_trust_server_certificate():
    source = (REPO_ROOT / "bin" / "gui_db_connection.py").read_text(encoding="utf-8")
    assert "TrustServerCertificate=yes" not in source
    assert "Trust server certificate (not recommended)" in source
