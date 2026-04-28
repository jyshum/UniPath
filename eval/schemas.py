"""Pydantic schema for Reddit admission extraction. Shared by eval and reddit_agent."""
from pydantic import BaseModel
from typing import Literal, Optional


class AdmissionExtraction(BaseModel):
    relevant: bool
    school: Optional[str] = None
    program: Optional[str] = None
    decision: Optional[Literal["Accepted", "Rejected", "Waitlisted", "Deferred"]] = None
    core_avg: Optional[float] = None
    ec_raw: Optional[str] = None
    province: Optional[str] = None
    citizenship: Optional[str] = None
