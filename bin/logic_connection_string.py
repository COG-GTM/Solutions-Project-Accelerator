# -*- coding: utf-8 -*-
"""
Helpers for keeping the SQL Server password out of logs and ``config.ini``.

ODBC connection strings are ``KEY=value;`` pairs. A value that contains ``;``,
``{`` or ``}`` (or leading/trailing spaces) must be wrapped in braces with any
``}`` doubled. These helpers only touch the ``PWD`` / ``Password`` attribute.
"""

_PASSWORD_KEYS = ('pwd', 'password')
_LOGIN_KEYS = ('uid', 'user id')


def _attributes(connection_string):
    """
    Yield ``(key, segment, value)`` for each top-level ``KEY=value;`` pair.

    ``key`` is lower-cased (``None`` for a segment without ``=``), ``segment`` is the
    raw text including its trailing ``;`` and ``value`` is the raw (still braced) value.
    Semicolons inside ``{...}`` values do not split attributes.
    """
    text, i, n = connection_string, 0, len(connection_string)
    while i < n:
        equals, semicolon = text.find('=', i), text.find(';', i)
        if equals == -1 or -1 < semicolon < equals:
            end = n if semicolon == -1 else semicolon + 1
            yield None, text[i:end], ''
            i = end
            continue
        j = equals + 1
        while j < n and text[j].isspace():
            j += 1
        value_end = j
        if j < n and text[j] == '{':
            value_end = j + 1
            while value_end < n:
                if text[value_end] == '}':
                    if text.startswith('}}', value_end):
                        value_end += 2
                        continue
                    value_end += 1
                    break
                value_end += 1
        semicolon = text.find(';', value_end)
        end = n if semicolon == -1 else semicolon + 1
        value = text[j:value_end] if value_end > j else text[j:end].rstrip(';')
        yield text[i:equals].strip().lower(), text[i:end], value
        i = end


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
    Remove every top-level password attribute from ``connection_string``.

    :return: ``(connection_string_without_password, password)``; ``password``
        is the last value (the one ODBC uses), or ``None`` when the string has no
        ``PWD`` / ``Password`` attribute.
    """
    kept, password = [], None
    for key, segment, value in _attributes(connection_string or ''):
        if key in _PASSWORD_KEYS:
            password = _unquote_odbc_value(value.strip())
        else:
            kept.append(segment)
    return ''.join(kept), password


def add_password(connection_string, password):
    """Return ``connection_string`` with ``PWD=<password>;`` appended."""
    if connection_string and not connection_string.endswith(';'):
        connection_string += ';'
    return connection_string + 'PWD=' + quote_odbc_value(password) + ';'


def uses_sql_login(connection_string):
    """True when the connection string authenticates with a SQL Server login."""
    return any(key in _LOGIN_KEYS for key, _, _ in _attributes(connection_string or ''))


def redact_connection_string(connection_string):
    """Return ``connection_string`` without its password attribute, for logging."""
    return split_password(connection_string)[0]
