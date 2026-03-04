"""FastAPI最小ルーター雛形のテスト。"""

from __future__ import annotations

import pytest

from web.fastapi_app import _is_fastapi_available, create_fastapi_app


def test_create_fastapi_app_未導入時はエラー(monkeypatch: pytest.MonkeyPatch) -> None:
    """FastAPI未導入時は明示エラーを返す。"""
    monkeypatch.setattr("web.fastapi_app._is_fastapi_available", lambda: False)

    with pytest.raises(RuntimeError, match="fastapi"):
        create_fastapi_app()


def test_create_fastapi_app_ヘルスチェックが応答する() -> None:
    """導入済み環境では最小ルーターが応答する。"""
    if not _is_fastapi_available():
        pytest.skip("fastapi 未導入のためスキップ")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    app = create_fastapi_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "data": {"status": "healthy"}}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
