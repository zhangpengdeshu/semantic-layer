"""API 依赖：开发期用户上下文与角色守卫。"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header


@dataclass(slots=True)
class UserContext:
    user_id: str
    roles: list[str]


def current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_roles: str | None = Header(default=None, alias="X-Roles"),
) -> UserContext:
    user_id = x_user_id or "dev-user"
    roles = [item.strip() for item in (x_roles or "admin,modeler").split(",") if item.strip()]
    return UserContext(user_id=user_id, roles=roles)


def require_role(user: UserContext, *roles: str) -> None:
    if "admin" in user.roles:
        return
    if not set(user.roles).intersection(roles):
        from app.semantic.services.errors import PermissionDeniedError

        raise PermissionDeniedError("当前角色无权执行该操作", detail={"roles": list(roles)})


def writer_user(user: UserContext = Depends(current_user)) -> UserContext:
    """建模写操作：管理员 / 建模者 / 数据工程师。"""
    require_role(user, "modeler", "engineer")
    return user


def reviewer_user(user: UserContext = Depends(current_user)) -> UserContext:
    """认证决策：管理员 / 评审者。"""
    require_role(user, "reviewer")
    return user


def admin_user(user: UserContext = Depends(current_user)) -> UserContext:
    """发布、回滚等高风险操作：仅管理员。"""
    require_role(user)
    return user
