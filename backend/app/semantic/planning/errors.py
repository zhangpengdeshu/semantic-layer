"""规划阶段错误。"""

from __future__ import annotations


class PlanError(Exception):
    def __init__(self, code: str, message: str, *, detail: object = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail