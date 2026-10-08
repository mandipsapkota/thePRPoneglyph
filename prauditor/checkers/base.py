from enum import Enum
from pydantic import BaseModel

class Status(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIABLE = "UNVERIFIABLE"

class CheckResult(BaseModel):
    claim: dict
    status: Status
    evidence: str
