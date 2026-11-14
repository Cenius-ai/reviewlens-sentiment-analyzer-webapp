"""JSON API. Every route except ``/api/health`` requires a credential.

Accepts either the signed session cookie (what the browser holds) or HTTP Basic
(what scripts use) - both resolve against the same PBKDF2 user table.
"""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import auth, config
from ..services import analyze_service, batch_service, history_service, sample_service

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    text: str = Field(default="", max_length=50_000)


def require_user(request: Request) -> sqlite3.Row:
    user = auth.user_from_request(
        cookies=request.cookies,
        authorization=request.headers.get("authorization"),
    )
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": 'Basic realm="Reviewlens"'},
        )
    return user


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "app": config.APP_NAME, "version": config.APP_VERSION}


@router.post("/analyze")
def analyze(payload: AnalyzeRequest, user: sqlite3.Row = Depends(require_user)) -> dict:
    try:
        return analyze_service.analyze_review(int(user["id"]), payload.text)
    except analyze_service.ReviewValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/samples")
def samples(user: sqlite3.Row = Depends(require_user)) -> dict:
    return {"samples": sample_service.list_sets()}


@router.get("/samples/{sample_id}")
def sample_detail(sample_id: int, user: sqlite3.Row = Depends(require_user)) -> dict:
    found = sample_service.get_set(sample_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Sample set not found")
    return found


@router.post("/batch")
def create_batch(
    file: UploadFile = File(...),
    text_column: str = Form(default=""),
    user: sqlite3.Row = Depends(require_user),
) -> dict:
    content = file.file.read()
    try:
        return batch_service.score_csv(int(user["id"]), file.filename or "upload.csv", text_column, content)
    except batch_service.BatchValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/batch/{batch_id}/download")
def download_batch(batch_id: int, user: sqlite3.Row = Depends(require_user)) -> Response:
    try:
        filename, payload = batch_service.build_download_csv(int(user["id"]), batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Batch not found") from exc
    return Response(
        content=payload.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/history")
def history(
    limit: int | None = Query(default=None, ge=1, le=500),
    user: sqlite3.Row = Depends(require_user),
) -> dict:
    return {"analyses": history_service.list_analyses(int(user["id"]), limit=limit)}
