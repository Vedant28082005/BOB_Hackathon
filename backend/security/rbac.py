"""RBAC roles and permission constants."""
from enum import Enum


class Role(str, Enum):
    analyst = "analyst"       # view review queue, read assessments
    admin   = "admin"         # configure thresholds, manage users, full access
    auditor = "auditor"       # read-only audit log access only


PERMISSIONS: dict[str, list[Role]] = {
    "assessment:read":   [Role.analyst, Role.admin, Role.auditor],
    "assessment:create": [Role.analyst, Role.admin],
    "assessment:review": [Role.analyst, Role.admin],
    "audit:read":        [Role.analyst, Role.admin, Role.auditor],
    "admin:config":      [Role.admin],
    "admin:users":       [Role.admin],
    "graph:read":        [Role.analyst, Role.admin, Role.auditor],
    "metrics:read":      [Role.analyst, Role.admin],
}
