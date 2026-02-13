import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")

from app.main import should_suppress_asyncio_write_send_assertion


def test_suppresses_selector_write_send_assertion():
    context = {
        "message": "Exception in callback _SelectorSocketTransport._write_send()",
        "exception": AssertionError("Data should not be empty"),
    }
    assert should_suppress_asyncio_write_send_assertion(context) is True


def test_does_not_suppress_other_assertions():
    context = {
        "message": "Exception in callback something_else",
        "exception": AssertionError("Data should not be empty"),
    }
    assert should_suppress_asyncio_write_send_assertion(context) is False
