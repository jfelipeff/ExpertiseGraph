from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class FirmIn(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    industry: str = ""
    notes: str = ""


class ChatIn(BaseModel):
    question: str = Field(..., min_length=1)


class ExpertIn(BaseModel):
    question: str = Field(
        default="Who should I talk to about AI strategy for telecom companies?"
    )


class JobOut(BaseModel):
    id: str
    status: str
    stage: str
    progress: int
    file_stages: dict[str, Any] = {}
    decisions: dict[str, Any] = {}
    stats: dict[str, Any] = {}
    error: Optional[str] = None
