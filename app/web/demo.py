"""Page-support endpoints for the public landing page.

These deliberately live OUTSIDE ``/api``: the JSON API under ``/api/*`` requires a
credential on every route except ``/api/health``, while the public overview page
must be usable by a first-time visitor. Nothing here touches user rows - one
route lists the seeded sample sets, the other scores a review statelessly.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services import analyze_service, sample_service

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoAnalyzeRequest(BaseModel):
    text: str = Field(default="", max_length=50_000)


@router.get("/samples")
def demo_samples() -> dict:
    """The seeded sample review sets shown on the landing page."""
    return {"samples": sample_service.list_sets()}


@router.post("/analyze")
def demo_analyze(payload: DemoAnalyzeRequest) -> dict:
    """Score one review without persisting it (the landing-page demo box)."""
    try:
        return analyze_service.analyze_review(user_id=0, text=payload.text, persist=False)
    except analyze_service.ReviewValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
