"""FastAPI最小ルーター雛形のテスト。"""

from __future__ import annotations

import pytest

from shared.auth import GENERIC_AUTH_ERROR_MESSAGE
from shared.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
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


def test_create_fastapi_app_売上エクスポートが応答する() -> None:
    """認証/CSRFヘッダーが揃うと売上エクスポートが成功する。"""
    if not _is_fastapi_available():
        pytest.skip("fastapi 未導入のためスキップ")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    app = create_fastapi_app()
    client = TestClient(app)

    csrf_token = "csrf-token-for-test"
    response = client.post(
        "/business/sales/export",
        headers={
            "X-User-Id": "tax-001",
            "X-User-Role": "tax_accountant",
            CSRF_HEADER_NAME: csrf_token,
        },
        cookies={
            CSRF_COOKIE_NAME: csrf_token,
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["data"]["resource"] == "sales"
    assert response.json()["data"]["executed_by"] == "tax-001"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_create_fastapi_app_売上エクスポート_認証ヘッダー欠落は401() -> None:
    """認証ヘッダーが欠落すると401を返す。"""
    if not _is_fastapi_available():
        pytest.skip("fastapi 未導入のためスキップ")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    app = create_fastapi_app()
    client = TestClient(app)

    csrf_token = "csrf-token-for-test"
    response = client.post(
        "/business/sales/export",
        headers={
            CSRF_HEADER_NAME: csrf_token,
        },
        cookies={
            CSRF_COOKIE_NAME: csrf_token,
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "ok": False,
        "error": GENERIC_AUTH_ERROR_MESSAGE,
    }


def test_create_fastapi_app_cspレポートを受信できる() -> None:
    """CSPレポート形式のJSONを受信すると200を返す。"""
    if not _is_fastapi_available():
        pytest.skip("fastapi 未導入のためスキップ")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    app = create_fastapi_app()
    client = TestClient(app)

    response = client.post(
        "/csp-report",
        json={
            "csp-report": {
                "document-uri": "https://example.com/report",
                "violated-directive": "script-src-elem",
                "effective-directive": "script-src",
                "blocked-uri": "https://cdn.example.com/lib.js",
                "original-policy": "default-src 'self'; report-uri /csp-report",
                "status-code": 200,
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["data"]["accepted"] is True
    assert isinstance(response.json()["data"]["persisted_id"], int)
    assert response.json()["data"]["persisted_id"] > 0
    assert response.json()["data"]["report_fields"] == [
        "blocked-uri",
        "document-uri",
        "effective-directive",
        "original-policy",
        "status-code",
        "violated-directive",
    ]


def test_create_fastapi_app_cspレポート_不正形式は400() -> None:
    """CSPレポート形式でないJSONは400を返す。"""
    if not _is_fastapi_available():
        pytest.skip("fastapi 未導入のためスキップ")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    app = create_fastapi_app()
    client = TestClient(app)

    response = client.post("/csp-report", json={"unexpected": "value"})

    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "error": "不正なリクエストです",
    }


def test_create_fastapi_app_cspレポート集計を取得できる() -> None:
    """CSPレポート受信後に集計ビューを取得できる。"""
    if not _is_fastapi_available():
        pytest.skip("fastapi 未導入のためスキップ")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    app = create_fastapi_app()
    client = TestClient(app)

    client.post(
        "/csp-report",
        json={
            "csp-report": {
                "document-uri": "https://example.com/summary-1",
                "violated-directive": "script-src-elem",
                "effective-directive": "script-src",
                "blocked-uri": "https://cdn.example.com/script.js",
                "original-policy": "default-src 'self'; report-uri /csp-report",
                "status-code": 200,
            }
        },
    )
    client.post(
        "/csp-report",
        json={
            "csp-report": {
                "document-uri": "https://example.com/summary-2",
                "violated-directive": "img-src",
                "effective-directive": "img-src",
                "blocked-uri": "https://cdn.example.com/image.png",
                "original-policy": "default-src 'self'; report-uri /csp-report",
                "status-code": 200,
            }
        },
    )

    response = client.get("/csp-report/summary?days=30&top=5&spike_threshold=1")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    data = response.json()["data"]
    assert data["range_days"] == 30
    assert data["total_reports"] >= 2
    assert data["spike_threshold"] == 1
    assert isinstance(data["period_counts"], list)
    directive_names = [item["directive"] for item in data["directive_counts"]]
    assert "script-src-elem" in directive_names
    assert "img-src" in directive_names
    spike_names = [item["directive"] for item in data["spike_directives"]]
    assert "script-src-elem" in spike_names
    assert "img-src" in spike_names


def test_create_fastapi_app_cspレポート集計_不正クエリは400() -> None:
    """集計APIで不正クエリパラメータは400を返す。"""
    if not _is_fastapi_available():
        pytest.skip("fastapi 未導入のためスキップ")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    app = create_fastapi_app()
    client = TestClient(app)

    response = client.get("/csp-report/summary?days=0")

    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "error": "不正なリクエストです",
    }


def test_create_fastapi_app_cspレポート集計_不正しきい値は400() -> None:
    """集計APIで不正なしきい値は400を返す。"""
    if not _is_fastapi_available():
        pytest.skip("fastapi 未導入のためスキップ")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    app = create_fastapi_app()
    client = TestClient(app)

    response = client.get("/csp-report/summary?spike_threshold=0")

    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "error": "不正なリクエストです",
    }
