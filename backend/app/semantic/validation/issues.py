"""统一校验问题结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Issue:
    code: str
    message: str
    level: str = "error"
    object_type: str = "model"
    object_id: int | None = None
    path: str | None = None
    suggestion: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def error(code: str, message: str, **kwargs: Any) -> Issue:
    return Issue(code=code, message=message, level="error", **kwargs)


def warning(code: str, message: str, **kwargs: Any) -> Issue:
    return Issue(code=code, message=message, level="warning", **kwargs)


def has_errors(issues: list[Issue]) -> bool:
    return any(item.level == "error" for item in issues)