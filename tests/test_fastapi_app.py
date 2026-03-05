"""FastAPI最小ルーター雛形のテスト。"""

from __future__ import annotations

import json

import pytest

from shared.auth import GENERIC_AUTH_ERROR_MESSAGE
from shared.csp_report import CspSpikeAlertSender
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
    assert isinstance(data["alert_dispatched"], bool)


def test_create_fastapi_app_cspレポート集計_急増時に通知送信される(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Webhook設定がある場合、急増検知で通知送信される。"""
    if not _is_fastapi_available():
        pytest.skip("fastapi 未導入のためスキップ")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    sent_payloads: list[dict[str, object]] = []

    sender = CspSpikeAlertSender(
        endpoint_url="https://hooks.example.com/csp",
        transport=lambda _endpoint_url, _headers, body, _timeout: sent_payloads.append(
            json.loads(body.decode("utf-8"))
        ),
    )

    monkeypatch.setattr("web.fastapi_app.create_csp_spike_alert_sender_from_env", lambda: sender)

    app = create_fastapi_app()
    client = TestClient(app)

    client.post(
        "/csp-report",
        json={
            "csp-report": {
                "document-uri": "https://example.com/spike-1",
                "violated-directive": "script-src-elem",
                "effective-directive": "script-src",
                "status-code": 200,
            }
        },
    )
    client.post(
        "/csp-report",
        json={
            "csp-report": {
                "document-uri": "https://example.com/spike-2",
                "violated-directive": "script-src-elem",
                "effective-directive": "script-src",
                "status-code": 200,
            }
        },
    )

    response = client.get("/csp-report/summary?days=30&top=5&spike_threshold=1")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    data = response.json()["data"]
    assert data["alert_dispatched"] is True
    assert len(sent_payloads) == 1
    assert sent_payloads[0]["event"] == "csp_spike_detected"


def test_create_fastapi_app_cspレポート集計_通知失敗時も200を返す(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """通知失敗時でも集計APIは200で応答し alert_dispatched は false。"""
    if not _is_fastapi_available():
        pytest.skip("fastapi 未導入のためスキップ")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    def failing_transport(_: str, __: dict[str, str], ___: bytes, ____: float) -> None:
        raise RuntimeError("webhook unavailable")

    sender = CspSpikeAlertSender(
        endpoint_url="https://hooks.example.com/csp",
        max_retries=1,
        retry_backoff_seconds=0.1,
        transport=failing_transport,
        sleeper=lambda _: None,
    )

    monkeypatch.setattr("web.fastapi_app.create_csp_spike_alert_sender_from_env", lambda: sender)

    app = create_fastapi_app()
    client = TestClient(app)

    client.post(
        "/csp-report",
        json={
            "csp-report": {
                "document-uri": "https://example.com/spike-1",
                "violated-directive": "script-src-elem",
                "effective-directive": "script-src",
                "status-code": 200,
            }
        },
    )

    response = client.get("/csp-report/summary?days=30&top=5&spike_threshold=1")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["data"]["alert_dispatched"] is False


def test_create_fastapi_app_cspレポート集計_同一directiveはクールダウン抑制(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一directive通知はクールダウン内で2回目を抑制する。"""
    if not _is_fastapi_available():
        pytest.skip("fastapi 未導入のためスキップ")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    sent_payloads: list[dict[str, object]] = []

    sender = CspSpikeAlertSender(
        endpoint_url="https://hooks.example.com/csp",
        transport=lambda _endpoint_url, _headers, body, _timeout: sent_payloads.append(
            json.loads(body.decode("utf-8"))
        ),
        sleeper=lambda _: None,
    )

    monkeypatch.setattr("web.fastapi_app.create_csp_spike_alert_sender_from_env", lambda: sender)
    monkeypatch.setattr("web.fastapi_app.get_csp_spike_alert_cooldown_minutes_from_env", lambda: 60)

    app = create_fastapi_app()
    client = TestClient(app)

    client.post(
        "/csp-report",
        json={
            "csp-report": {
                "document-uri": "https://example.com/cooldown-1",
                "violated-directive": "script-src-elem",
                "effective-directive": "script-src",
                "status-code": 200,
            }
        },
    )

    first = client.get("/csp-report/summary?days=30&top=5&spike_threshold=1")
    second = client.get("/csp-report/summary?days=30&top=5&spike_threshold=1")

    assert first.status_code == 200
    assert first.json()["ok"] is True
    assert first.json()["data"]["alert_dispatched"] is True

    assert second.status_code == 200
    assert second.json()["ok"] is True
    assert second.json()["data"]["alert_dispatched"] is False
    assert len(sent_payloads) == 1


def test_create_fastapi_app_cspレポート集計_高増加率はクールダウン解除で通知(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一directiveでも高増加率閾値を超えると2回目も通知する。"""
    if not _is_fastapi_available():
        pytest.skip("fastapi 未導入のためスキップ")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    sent_payloads: list[dict[str, object]] = []

    sender = CspSpikeAlertSender(
        endpoint_url="https://hooks.example.com/csp",
        transport=lambda _endpoint_url, _headers, body, _timeout: sent_payloads.append(
            json.loads(body.decode("utf-8"))
        ),
        sleeper=lambda _: None,
    )

    monkeypatch.setattr("web.fastapi_app.create_csp_spike_alert_sender_from_env", lambda: sender)
    monkeypatch.setattr("web.fastapi_app.get_csp_spike_alert_cooldown_minutes_from_env", lambda: 60)
    monkeypatch.setattr(
        "web.fastapi_app.get_csp_spike_alert_priority_increase_ratio_threshold_from_env",
        lambda: 1.0,
    )

    app = create_fastapi_app()
    client = TestClient(app)

    client.post(
        "/csp-report",
        json={
            "csp-report": {
                "document-uri": "https://example.com/cooldown-bypass-1",
                "violated-directive": "script-src-elem",
                "effective-directive": "script-src",
                "status-code": 200,
            }
        },
    )

    first = client.get("/csp-report/summary?days=30&top=5&spike_threshold=1")
    second = client.get("/csp-report/summary?days=30&top=5&spike_threshold=1")

    assert first.status_code == 200
    assert first.json()["ok"] is True
    assert first.json()["data"]["alert_dispatched"] is True

    assert second.status_code == 200
    assert second.json()["ok"] is True
    assert second.json()["data"]["alert_dispatched"] is True
    assert len(sent_payloads) == 2


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
