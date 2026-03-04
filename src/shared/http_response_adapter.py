"""ApiResponse を HTTP 応答形式へ変換するアダプタ。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shared.api_handlers import ApiResponse
    from shared.session import SessionCookie


@dataclass(frozen=True)
class HttpHeader:
    """HTTP ヘッダーの1項目。"""

    name: str
    value: str

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if not self.name:
            raise ValueError("ヘッダー名は必須です")
        if "\n" in self.name or "\r" in self.name or "\n" in self.value or "\r" in self.value:
            raise ValueError("ヘッダーに改行は指定できません")


@dataclass(frozen=True)
class HttpResponseEnvelope:
    """フレームワークへ橋渡しするHTTP応答データ。"""

    status_code: int
    body: dict[str, Any]
    headers: tuple[HttpHeader, ...]

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if self.status_code < 100 or self.status_code > 599:
            raise ValueError("status_code は 100〜599 である必要があります")
        if not self.body:
            raise ValueError("body は必須です")


def _to_set_cookie_header_value(cookie: SessionCookie) -> str:
    """SessionCookie を Set-Cookie ヘッダー値へ変換する。"""
    parts = [
        f"{cookie.name}={cookie.value}",
        f"Path={cookie.path}",
        f"Max-Age={cookie.max_age}",
        f"SameSite={cookie.same_site}",
    ]
    if cookie.secure:
        parts.append("Secure")
    if cookie.http_only:
        parts.append("HttpOnly")

    return "; ".join(parts)


def adapt_api_response_to_http(api_response: ApiResponse) -> HttpResponseEnvelope:
    """ApiResponse を HTTP 応答へ転写しやすい形式へ変換する。"""
    headers: list[HttpHeader] = [
        HttpHeader(name=key, value=value) for key, value in api_response.headers.items()
    ]

    for cookie in api_response.set_cookies:
        headers.append(
            HttpHeader(
                name="Set-Cookie",
                value=_to_set_cookie_header_value(cookie),
            )
        )

    return HttpResponseEnvelope(
        status_code=api_response.status_code,
        body=dict(api_response.body),
        headers=tuple(headers),
    )
