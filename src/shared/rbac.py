"""ロールベースアクセス制御（RBAC）の共通ロジック。"""

from __future__ import annotations

from collections.abc import Mapping

from shared.auth import AuthContext, require_active_authenticated_user
from shared.exceptions import AuthorizationError


AUTHORIZATION_ERROR_MESSAGE = "この操作を実行する権限がありません"

VALID_ACTIONS = {
    "read",
    "create",
    "update",
    "delete",
    "approve",
    "export",
}


PERMISSIONS_BY_ROLE: Mapping[str, Mapping[str, set[str]]] = {
    "admin": {
        "*": {"*"},
    },
    "manager": {
        "report": {"read", "create", "update"},
        "sales": {"read", "create", "update"},
        "shift": {"read", "create", "update"},
        "attendance_summary": {"read"},
        "kpi": {"read"},
        "labor_cost_summary": {"read"},
    },
    "labor_consultant": {
        "attendance": {"read", "export"},
        "shift": {"read", "export"},
        "payroll": {"read", "export"},
        "kpi": {"read", "export"},
    },
    "tax_accountant": {
        "report": {"read", "export"},
        "sales": {"read", "export"},
        "expense": {"read", "export"},
        "petty_cash": {"read", "export"},
        "purchase": {"read", "export"},
        "labor_cost_summary": {"read", "export"},
        "profit_loss": {"read", "export"},
        "kpi": {"read", "export"},
    },
    "employee": {},
}


def normalize_role(role: str) -> str:
    """ロール文字列を標準化する。"""
    normalized_role = role.strip().lower()
    if not normalized_role:
        raise ValueError("ロールは必須です")
    return normalized_role


def has_permission(role: str, resource: str, action: str) -> bool:
    """指定ロールにリソース操作の権限があるかを判定する。"""
    normalized_role = normalize_role(role)
    normalized_resource = resource.strip()
    normalized_action = action.strip().lower()

    if not normalized_resource:
        raise ValueError("リソースは必須です")
    if normalized_action not in VALID_ACTIONS:
        raise ValueError("不正な操作種別です")

    role_permissions = PERMISSIONS_BY_ROLE.get(normalized_role)
    if role_permissions is None:
        return False

    wildcard_permissions = role_permissions.get("*")
    if wildcard_permissions is not None and (
        "*" in wildcard_permissions or normalized_action in wildcard_permissions
    ):
        return True

    resource_permissions = role_permissions.get(normalized_resource)
    if resource_permissions is None:
        return False

    return normalized_action in resource_permissions


def require_permission(
    context: AuthContext | None,
    *,
    resource: str,
    action: str,
) -> AuthContext:
    """認証済みかつ指定権限を持つユーザーを必須とする。"""
    authenticated_context = require_active_authenticated_user(context)

    if not has_permission(authenticated_context.role, resource, action):
        raise AuthorizationError(AUTHORIZATION_ERROR_MESSAGE)

    return authenticated_context
