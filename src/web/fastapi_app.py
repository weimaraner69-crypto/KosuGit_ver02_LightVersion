"""FastAPI 最小ルーター雛形。"""

from __future__ import annotations

import importlib.util
from typing import Any

from shared.api_handlers import ApiResponse
from shared.fastapi_response_adapter import adapt_api_response_to_fastapi


def _is_fastapi_available() -> bool:
    """FastAPI 依存が導入済みか判定する。"""
    try:
        return importlib.util.find_spec("fastapi") is not None
    except ModuleNotFoundError:
        return False


def create_fastapi_app() -> Any:
    """FastAPI アプリを生成する。"""
    if not _is_fastapi_available():
        raise RuntimeError(
            "fastapi がインストールされていません。`pip install '.[web]'` を実行してください"
        )

    from fastapi import FastAPI  # type: ignore[import-not-found]

    def health_check_handler() -> Any:
        """ヘルスチェックのサンプルエンドポイント。"""
        api_response = ApiResponse(
            status_code=200,
            body={
                "ok": True,
                "data": {
                    "status": "healthy",
                },
            },
        )
        return adapt_api_response_to_fastapi(api_response)

    app = FastAPI(title="business-management-system", version="0.1.0")

    app.get("/health")(health_check_handler)

    return app
