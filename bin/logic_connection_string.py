# -*- coding: utf-8 -*-
"""
Helpers for keeping the SQL Server password out of logs and ``config.ini``.

ODBC connection strings are ``KEY=value;`` pairs. A value that contains ``;``,
``{`` or ``}`` (or leading/trailing spaces) must be wrapped in braces with any
``}`` doubled. These helpers only touch the ``PWD`` / ``Password`` attribute.
"""

import re

_PASSWORD_ATTRIBUTE = re.compile(
    r'(?i)(?:^|(?<=;))\s*(?:PWD|Password)\s*=\s*(\{(?:[^}]|\}\})*\}|[^;]*);?')
_LOGIN_ATTRIBUTE = re.compile(r'(?i)(?:^|(?<=;))\s*(?:UID|User ID)\s*=')


def quote_odbc_value(value):
    """Return ``value`` escaped for use as an ODBC connection string value."""
    if value and (any(c in value for c in ';{}') or value != value.strip()):
        return '{' + value.replace('}', '}}') + '}'
    return value


def _unquote_odbc_value(value):
    if value.startswith('{') and value.endswith('}'):
        return value[1:-1].replace('}}', '}')
    return value


def split_password(connection_string):
    """
    Remove every password attribute from ``connection_string``.

    :return: ``(connection_string_without_password, password)``; ``password``
        is the last value (the one ODBC uses), or ``None`` when the string has no
        ``PWD`` / ``Password`` attribute.
    """
    stripped, password = connection_string or '', None
    match = _PASSWORD_ATTRIBUTE.search(stripped)
    while match:
        password = _unquote_odbc_value(match.group(1).strip())
        stripped = stripped[:match.start()] + stripped[match.end():]
        match = _PASSWORD_ATTRIBUTE.search(stripped)
    return stripped, password


def add_password(connection_string, password):
    """Return ``connection_string`` with ``PWD=<password>;`` appended."""
    if connection_string and not connection_string.endswith(';'):
        connection_string += ';'
    return connection_string + 'PWD=' + quote_odbc_value(password) + ';'


def uses_sql_login(connection_string):
    """True when the connection string authenticates with a SQL Server login."""
    return bool(_LOGIN_ATTRIBUTE.search(connection_string or ''))


def redact_connection_string(connection_string):
    """Return ``connection_string`` without its password attribute, for logging."""
    return split_password(connection_string)[0]
