from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CreateRunRequest(BaseModel):
    task: str
    max_revisions: int | None = None


class ResumeRequest(BaseModel):
    decision: Literal["approve", "reject", "edit"]
    edited_content: str | None = None


class RunSummary(BaseModel):
    run_id: str
    task: str
    status: str
    max_revisions: int
    created_at: str
    updated_at: str


class CheckpointSummary(BaseModel):
    checkpoint_id: str
    next: list[str]
    step: int | None = None
