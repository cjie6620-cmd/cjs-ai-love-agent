from contextlib import contextmanager

from app.infra.db import bootstrap as db_bootstrap
from app.infra.vector import bootstrap as vector_bootstrap


def test_initialize_mysql_tables_calls_create_all(monkeypatch) -> None:
    called: dict[str, object] = {}

    monkeypatch.setattr(db_bootstrap.get_settings(), "db_auto_create_tables", True)

    def fake_create_all(*, bind) -> None:
        called["bind"] = bind

    monkeypatch.setattr(db_bootstrap.Base.metadata, "create_all", fake_create_all)
    db_bootstrap.initialize_mysql_tables()

    assert called["bind"] is db_bootstrap.get_engine()


def test_initialize_vector_tables_creates_extension_and_tables(monkeypatch) -> None:
    executed_sql: list[str] = []
    called: dict[str, object] = {}

    monkeypatch.setattr(vector_bootstrap.get_settings(), "vector_auto_create_tables", True)

    class FakeConnection:
        def execute(self, statement) -> None:
            compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
            executed_sql.append(compiled)

    @contextmanager
    def fake_begin(self):
        yield FakeConnection()

    def fake_create_all(*, bind) -> None:
        called["bind"] = bind

    class FakeEngine:
        begin = fake_begin

    monkeypatch.setattr(vector_bootstrap, "get_vector_engine", lambda: FakeEngine())
    monkeypatch.setattr(vector_bootstrap.VectorBase.metadata, "create_all", fake_create_all)

    vector_bootstrap.initialize_vector_tables()

    assert any("CREATE EXTENSION IF NOT EXISTS vector" in sql for sql in executed_sql)
    assert called["bind"] is not None
