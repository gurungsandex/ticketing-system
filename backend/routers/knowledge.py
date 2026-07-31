"""
Knowledge management: analytics, AI-assisted draft generation, and the
KB article approval workflow.

Approval rules (enforced here, not just in the UI):
  * Generated content is always saved as workflow_status='draft'.
  * Only a super_admin may approve/publish/reject an article.
  * Nothing is ever auto-published.
"""
import json
from typing import List, Optional

import config
import models
import schemas
from auth import get_current_admin, require_super_admin
from database import get_db
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from services import kb_analysis
from sqlalchemy.orm import Session
from utils import utcnow

router = APIRouter()

VALID_WORKFLOW = {"draft", "approved", "published", "rejected"}


# ── Analytics ─────────────────────────────────────────

@router.get("/kb/analysis")
def get_analysis(
    min_cluster_size: int = Query(2, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    """Mine ticket history for frequent problems, resolutions, and KB candidates."""
    return kb_analysis.analyze(db, min_cluster_size=min_cluster_size)


# ── Draft generation (creates a DRAFT only) ───────────

@router.post("/kb/generate-draft", response_model=schemas.KBArticleResponse)
def generate_draft(
    cluster: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    context = kb_analysis.build_cluster_context(db, cluster)
    if not context:
        raise HTTPException(status_code=404, detail=f"No tickets found for cluster '{cluster}'")

    draft = kb_analysis.generate_draft(context)
    article = models.KBArticle(
        title=draft["title"],
        category=draft["category"],
        problem_summary=draft["problem_summary"],
        content=draft["content"],
        article_type="playbook",
        source="ai_generated",
        workflow_status="draft",   # NEVER auto-published
        tags=draft["tags"],
        source_meta=json.dumps({
            "cluster": cluster,
            "ticket_count": context["ticket_count"],
            "resolved_count": context["resolved_count"],
        }),
        created_by=current_user.username,
        created_at=utcnow(),
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


# ── Article CRUD ──────────────────────────────────────

@router.get("/kb/articles", response_model=List[schemas.KBArticleSummary])
def list_articles(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    q = db.query(models.KBArticle)
    if status:
        q = q.filter(models.KBArticle.workflow_status == status)
    if category:
        q = q.filter(models.KBArticle.category == category)
    return q.order_by(models.KBArticle.updated_at.desc().nullslast(),
                      models.KBArticle.created_at.desc()).all()


@router.get("/kb/articles/{article_id}", response_model=schemas.KBArticleResponse)
def get_article(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    a = db.query(models.KBArticle).filter(models.KBArticle.id == article_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Article not found")
    return a


@router.post("/kb/articles", response_model=schemas.KBArticleResponse)
def create_article(
    body: schemas.KBArticleCreate,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    title = (body.title or "").strip()
    content = (body.content or "").strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="Title and content are required.")
    a = models.KBArticle(
        title=title[: config.MAX_GENERIC_TEXT_LEN],
        category=(body.category or None),
        problem_summary=(body.problem_summary or None),
        content=content,
        article_type=(body.article_type or "article"),
        source="manual",
        workflow_status="draft",
        tags=(body.tags or None),
        created_by=current_user.username,
        created_at=utcnow(),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.patch("/kb/articles/{article_id}", response_model=schemas.KBArticleResponse)
def update_article(
    article_id: int,
    body: schemas.KBArticleUpdate,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    a = db.query(models.KBArticle).filter(models.KBArticle.id == article_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Article not found")
    # Editing an approved/published article sends it back to draft for re-review.
    changed = False
    for field in ("title", "category", "problem_summary", "content", "article_type", "tags"):
        val = getattr(body, field)
        if val is not None:
            setattr(a, field, val)
            changed = True
    if changed and a.workflow_status in ("approved", "published"):
        a.workflow_status = "draft"
        a.approved_by = None
        a.approved_at = None
    a.updated_at = utcnow()
    db.commit()
    db.refresh(a)
    return a


@router.delete("/kb/articles/{article_id}")
def delete_article(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(require_super_admin),
):
    a = db.query(models.KBArticle).filter(models.KBArticle.id == article_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Article not found")
    db.delete(a)
    db.commit()
    return {"deleted": article_id}


# ── Approval workflow (super_admin only) ──────────────

@router.post("/kb/articles/{article_id}/review", response_model=schemas.KBArticleResponse)
def review_article(
    article_id: int,
    decision: str = Body(..., embed=True),   # approved | published | rejected | draft
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(require_super_admin),
):
    if decision not in VALID_WORKFLOW:
        raise HTTPException(status_code=400, detail=f"Invalid decision. One of {VALID_WORKFLOW}")
    a = db.query(models.KBArticle).filter(models.KBArticle.id == article_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Article not found")
    a.workflow_status = decision
    if decision in ("approved", "published"):
        a.approved_by = current_user.username
        a.approved_at = utcnow()
    else:
        a.approved_by = None
        a.approved_at = None
    a.updated_at = utcnow()
    db.commit()
    db.refresh(a)
    return a
