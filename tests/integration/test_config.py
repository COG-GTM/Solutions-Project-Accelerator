"""Integration tests for bin/logic_config.py.

Config resolves its INI path from ``__main__.__file__``, so every test here uses
the ``tmp_config_home`` fixture to keep the real temp/config.ini untouched.
"""

import pytest

from bin.logic_config import Config

pytestmark = pytest.mark.integration


class TestFirstRun:
    def test_defaults_are_seeded_when_no_ini_exists(self, tmp_config_home):
        config = Config()
        assert config.get_win_geometry() == "1269x779+256+89"
        assert config.get_win_state() == "normal"

    def test_save_writes_the_ini_to_the_temp_folder(self, tmp_config_home):
        config = Config()
        config.save()
        assert (tmp_config_home / "temp" / "config.ini").is_file()

    def test_no_ini_is_written_until_save_is_called(self, tmp_config_home):
        Config()
        assert not (tmp_config_home / "temp" / "config.ini").exists()

    def test_opened_project_defaults_to_none_sentinel(self, tmp_config_home):
        assert Config().get_opened_project() == Config.DEFAULT_PROJECT_OPEN


class TestRoundTrip:
    @pytest.mark.parametrize("geometry", ["800x600+0+0", "1920x1080+100+50"])
    def test_window_geometry_persists(self, tmp_config_home, geometry):
        first = Config()
        first.set_win_geometry(geometry)
        first.save()

        assert Config().get_win_geometry() == geometry

    def test_window_state_persists(self, tmp_config_home):
        first = Config()
        first.set_win_state("zoomed")
        first.save()

        assert Config().get_win_state() == "zoomed"

    @pytest.mark.parametrize("value", [True, False])
    def test_vertical_text_flag_persists_as_a_bool(self, tmp_config_home, value):
        first = Config()
        first.set_ocr_vertical_text_rotated_up(value)
        first.save()

        reloaded = Config().get_ocr_vertical_text_rotated_up()
        assert reloaded is value

    def test_objects_filter_round_trips_through_json(self, tmp_config_home):
        payload = {"type": ["Valve", "Pump"], "page": 3}
        first = Config()
        first.set_objects_filter(payload)
        first.save()

        assert Config().get_objects_filter() == payload

    def test_connection_string_persists(self, tmp_config_home):
        first = Config()
        first.set_connection_string("Driver=SQL;Server=localhost")
        first.save()

        assert Config().get_connection_string() == "Driver=SQL;Server=localhost"

    def test_option_case_is_preserved(self, tmp_config_home):
        # optionxform is overridden so ACM/HMI keys keep their casing.
        config = Config()
        config.set_win_geometry("800x600+0+0")
        config.save()

        text = (tmp_config_home / "temp" / "config.ini").read_text(encoding="utf-8")
        assert "Geometry" in text


class TestUserId:
    def test_first_call_generates_an_id_and_flags_it_as_new(self, tmp_config_home):
        user_id, was_generated = Config().get_user_id()
        assert was_generated is True
        assert user_id

    def test_a_persisted_id_is_reused_and_not_flagged_as_new(self, tmp_config_home):
        first = Config()
        original_id, _ = first.get_user_id()
        first.save()

        reloaded_id, was_generated = Config().get_user_id()
        assert reloaded_id == original_id
        assert was_generated is False

    def test_id_is_stable_within_one_instance(self, tmp_config_home):
        config = Config()
        assert config.get_user_id()[0] == config.get_user_id()[0]


class TestMissingKeysFallBackToDefaults:
    """A partially written or hand-edited ini must not crash the app."""

    def test_empty_ini_yields_defaults(self, tmp_config_home):
        (tmp_config_home / "temp" / "config.ini").write_text("", encoding="utf-8")
        config = Config()
        assert config.get_win_geometry() == "1269x779+256+89"
        assert config.get_objects_filter() == {}
        assert config.get_connection_string() == ""

    def test_section_present_but_key_missing(self, tmp_config_home):
        (tmp_config_home / "temp" / "config.ini").write_text("[Window]\n", encoding="utf-8")
        assert Config().get_win_geometry() == "1269x779+256+89"

    def test_opened_path_is_blank_when_the_stored_path_no_longer_exists(self, tmp_config_home):
        (tmp_config_home / "temp" / "config.ini").write_text(
            "[Window]\nOpenedPath = C:\\does\\not\\exist\n", encoding="utf-8")
        assert Config().get_opened_path() == ""


class _FakeDpapi:
    """Stands in for pywin32's win32crypt: reversible, but never stores the plaintext."""

    @staticmethod
    def CryptProtectData(data, description, *args):
        return b'DPAPI:' + bytes(b ^ 0x5A for b in data)

    @staticmethod
    def CryptUnprotectData(blob, *args):
        assert blob.startswith(b'DPAPI:')
        return 'desc', bytes(b ^ 0x5A for b in blob[len(b'DPAPI:'):])


@pytest.fixture
def fake_dpapi(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'win32crypt', _FakeDpapi)


SQL_LOGIN = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=acm01;DATABASE=ACM;'
             'UID=alice;PWD=Hunter2-acm;TrustServerCertificate=yes;')
SECRET = 'Hunter2-acm'


class TestSqlPasswordIsNotStoredInTheIni:
    def _ini(self, home):
        return (home / "temp" / "config.ini").read_text(encoding="utf-8")

    def test_password_goes_to_the_dpapi_blob(self, tmp_config_home, fake_dpapi):
        first = Config()
        first.set_connection_string(SQL_LOGIN)
        first.save()

        ini = self._ini(tmp_config_home)
        assert SECRET not in ini
        assert 'PWD' not in ini
        assert 'UID=alice' in ini
        blob = (tmp_config_home / "temp" / "sql_password.dat").read_bytes()
        assert SECRET.encode() not in blob

        restored = Config().get_connection_string()
        assert 'PWD=Hunter2-acm;' in restored
        assert 'SERVER=acm01' in restored and 'TrustServerCertificate=yes' in restored

    def test_legacy_plaintext_password_is_migrated_on_first_read(self, tmp_config_home, fake_dpapi):
        (tmp_config_home / "temp" / "config.ini").write_text(
            "[SQL]\nConnection string = " + SQL_LOGIN + "\n", encoding="utf-8")

        assert Config().get_connection_string() == SQL_LOGIN
        assert SECRET not in self._ini(tmp_config_home)
        assert 'PWD=Hunter2-acm;' in Config().get_connection_string()

    def test_windows_authentication_forgets_a_saved_password(self, tmp_config_home, fake_dpapi):
        config = Config()
        config.set_connection_string(SQL_LOGIN)
        config.set_connection_string('DRIVER={x};SERVER=acm01;DATABASE=ACM;Trusted_Connection=yes;')
        assert not (tmp_config_home / "temp" / "sql_password.dat").exists()

    def test_clear_connection_string_removes_ini_entry_and_blob(self, tmp_config_home, fake_dpapi):
        config = Config()
        config.set_connection_string(SQL_LOGIN)
        config.clear_connection_string()
        config.save()

        assert Config().get_connection_string() == ''
        assert not (tmp_config_home / "temp" / "sql_password.dat").exists()

    def test_without_dpapi_the_password_is_dropped_not_written(self, tmp_config_home, monkeypatch):
        import sys
        monkeypatch.setitem(sys.modules, 'win32crypt', None)
        config = Config()
        config.set_connection_string(SQL_LOGIN)
        config.save()

        assert SECRET not in self._ini(tmp_config_home)
        assert not (tmp_config_home / "temp" / "sql_password.dat").exists()
        assert 'PWD' not in Config().get_connection_string()
