"""
================================================================================
Schemas de Request/Response da API
================================================================================

Define os modelos Pydantic para validação de entrada e documentação de saída.
"""

from .common import (
    APIResponse,
    ErrorResponse,
    ErrorDetail,
    SuccessResponse,
)
from .generate import (
    GenerateRequest,
    GenerateResponse,
)
from .validate import (
    ValidateRequest,
    ValidateResponse,
    ValidationIssue,
)
from .execute import (
    ExecuteRequest,
    ExecuteResponse,
    StepResultSchema,
)
from .history import (
    HistoryListResponse,
    HistoryRecordSchema,
    HistoryFilterParams,
)
from .workspace import (
    WorkspaceInitRequest,
    WorkspaceInitResponse,
)
from .plans import (
    PlanSummary,
    PlansListResponse,
    PlanDetailResponse,
    PlanVersionSummary,
    PlanVersionsResponse,
    PlanDiffChange,
    PlanDiffResponse,
    PlanRestoreRequest,
    PlanRestoreResponse,
)

__all__ = [
    # Common
    "APIResponse",
    "ErrorResponse",
    "ErrorDetail",
    "SuccessResponse",
    # Generate
    "GenerateRequest",
    "GenerateResponse",
    # Validate
    "ValidateRequest",
    "ValidateResponse",
    "ValidationIssue",
    # Execute
    "ExecuteRequest",
    "ExecuteResponse",
    "StepResultSchema",
    # History
    "HistoryListResponse",
    "HistoryRecordSchema",
    "HistoryFilterParams",
    # Workspace
    "WorkspaceInitRequest",
    "WorkspaceInitResponse",
    # Plans
    "PlanSummary",
    "PlansListResponse",
    "PlanDetailResponse",
    "PlanVersionSummary",
    "PlanVersionsResponse",
    "PlanDiffChange",
    "PlanDiffResponse",
    "PlanRestoreRequest",
    "PlanRestoreResponse",
]
