"""语义层领域枚举。"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - 便于日志
        return self.value


class ModelStatus(StrEnum):
    DRAFT = "draft"
    CERTIFIED = "certified"
    DEPRECATED = "deprecated"


class FieldSemanticType(StrEnum):
    KEY = "key"
    DIMENSION = "dimension"
    TIME = "time"
    MEASURE = "measure"
    UNKNOWN = "unknown"


class DataType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    UNKNOWN = "unknown"


class DimensionType(StrEnum):
    CATEGORICAL = "categorical"
    TIME = "time"


class TimeGrain(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class Additivity(StrEnum):
    ADDITIVE = "additive"
    SEMI_ADDITIVE = "semi_additive"
    NON_ADDITIVE = "non_additive"


class Cardinality(StrEnum):
    ONE_TO_ONE = "1:1"
    ONE_TO_N = "1:N"
    N_TO_ONE = "N:1"
    N_TO_N = "N:N"


class JoinType(StrEnum):
    INNER = "inner"
    LEFT = "left"


class BindingType(StrEnum):
    DATASET = "dataset"
    TABLE = "table"
    VIEW = "view"
    SUBQUERY = "subquery"


class BindingStatus(StrEnum):
    DRAFT = "draft"
    CERTIFIED = "certified"
    DISABLED = "disabled"


class MetricType(StrEnum):
    SIMPLE = "simple"
    RATIO = "ratio"
    DERIVED = "derived"
    CUMULATIVE = "cumulative"
    CONVERSION = "conversion"


class MetricInputType(StrEnum):
    METRIC = "metric"
    MEASURE = "measure"


class MetricInputRole(StrEnum):
    NUMERATOR = "numerator"
    DENOMINATOR = "denominator"
    INPUT = "input"
    BASE = "base"
    CONVERSION = "conversion"


class IssueLevel(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationLevel(StrEnum):
    SEMANTIC = "semantic"
    QUERYABLE = "queryable"


class BindingState(StrEnum):
    UNBOUND = "unbound"
    PARTIAL = "partial"
    READY = "ready"


class Origin(StrEnum):
    MANUAL = "manual"
    IMPORT = "import"
    TEMPLATE = "template"
    AI = "ai"
