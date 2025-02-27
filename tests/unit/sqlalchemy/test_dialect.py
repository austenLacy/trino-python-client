from typing import Any, Dict, List
from unittest import mock

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.engine.url import URL

from trino.auth import BasicAuthentication
from trino.dbapi import Connection
from trino.sqlalchemy.dialect import CertificateAuthentication, JWTAuthentication, TrinoDialect
from trino.transaction import IsolationLevel


class TestTrinoDialect:
    def setup(self):
        self.dialect = TrinoDialect()

    @pytest.mark.parametrize(
        "url, expected_args, expected_kwargs",
        [
            (
                make_url("trino://user@localhost"),
                list(),
                dict(host="localhost", catalog="system", user="user", source="trino-sqlalchemy"),
            ),
            (
                make_url("trino://user@localhost:8080"),
                list(),
                dict(host="localhost", port=8080, catalog="system", user="user", source="trino-sqlalchemy"),
            ),
            (
                make_url("trino://user:pass@localhost:8080?source=trino-rulez"),
                list(),
                dict(
                    host="localhost",
                    port=8080,
                    catalog="system",
                    user="user",
                    auth=BasicAuthentication("user", "pass"),
                    http_scheme="https",
                    source="trino-rulez"
                ),
            ),
            (
                make_url(
                    'trino://user@localhost:8080?'
                    'session_properties={"query_max_run_time": "1d"}'
                    '&http_headers={"trino": 1}'
                    '&extra_credential=[("a", "b"), ("c", "d")]'
                    '&client_tags=[1, "sql"]'),
                list(),
                dict(
                    host="localhost",
                    port=8080,
                    catalog="system",
                    user="user",
                    source="trino-sqlalchemy",
                    session_properties={"query_max_run_time": "1d"},
                    http_headers={"trino": 1},
                    extra_credential=[("a", "b"), ("c", "d")],
                    client_tags=[1, "sql"]
                ),
            ),
        ],
    )
    def test_create_connect_args(self, url: URL, expected_args: List[Any], expected_kwargs: Dict[str, Any]):
        actual_args, actual_kwargs = self.dialect.create_connect_args(url)

        assert actual_args == expected_args
        assert actual_kwargs == expected_kwargs

    def test_create_connect_args_missing_user_when_specify_password(self):
        url = make_url("trino://:pass@localhost")
        with pytest.raises(ValueError, match="Username is required when specify password in connection URL"):
            self.dialect.create_connect_args(url)

    def test_create_connect_args_wrong_db_format(self):
        url = make_url("trino://abc@localhost/catalog/schema/foobar")
        with pytest.raises(ValueError, match="Unexpected database format catalog/schema/foobar"):
            self.dialect.create_connect_args(url)

    def test_get_default_isolation_level(self):
        isolation_level = self.dialect.get_default_isolation_level(mock.Mock())
        assert isolation_level == "AUTOCOMMIT"

    def test_isolation_level(self):
        dbapi_conn = Connection(host="localhost")

        self.dialect.set_isolation_level(dbapi_conn, "SERIALIZABLE")
        assert dbapi_conn._isolation_level == IsolationLevel.SERIALIZABLE

        isolation_level = self.dialect.get_isolation_level(dbapi_conn)
        assert isolation_level == "SERIALIZABLE"


def test_trino_connection_basic_auth():
    dialect = TrinoDialect()
    username = 'trino-user'
    password = 'trino-bunny'
    url = make_url(f'trino://{username}:{password}@host')
    _, cparams = dialect.create_connect_args(url)

    assert cparams['http_scheme'] == "https"
    assert isinstance(cparams['auth'], BasicAuthentication)
    assert cparams['auth']._username == username
    assert cparams['auth']._password == password


def test_trino_connection_jwt_auth():
    dialect = TrinoDialect()
    access_token = 'sample-token'
    url = make_url(f'trino://host/?access_token={access_token}')
    _, cparams = dialect.create_connect_args(url)

    assert cparams['http_scheme'] == "https"
    assert isinstance(cparams['auth'], JWTAuthentication)
    assert cparams['auth'].token == access_token


def test_trino_connection_certificate_auth():
    dialect = TrinoDialect()
    cert = '/path/to/cert.pem'
    key = '/path/to/key.pem'
    url = make_url(f'trino://host/?cert={cert}&key={key}')
    _, cparams = dialect.create_connect_args(url)

    assert cparams['http_scheme'] == "https"
    assert isinstance(cparams['auth'], CertificateAuthentication)
    assert cparams['auth']._cert == cert
    assert cparams['auth']._key == key
