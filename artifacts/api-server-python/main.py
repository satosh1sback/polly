import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, Response, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import get_db
from models import Poll, PollOption, Vote

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

CATEGORIES = [
    "Technology", "Science", "Politics", "Finance",
    "Society", "Environment", "Work & Career",
]


def timeago(dt: datetime) -> str:
    if dt is None:
        return ""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    s = int(diff.total_seconds())
    if s < 60:
        return "just now"
    if s < 3600:
        m = s // 60
        return f"{m} minute{'s' if m != 1 else ''} ago"
    if s < 86400:
        h = s // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    d = s // 86400
    return f"{d} day{'s' if d != 1 else ''} ago"


def is_active(poll: Poll) -> bool:
    if not poll.is_active:
        return False
    if poll.ends_at is None:
        return True
    ends = poll.ends_at
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    return ends > datetime.now(timezone.utc)


templates.env.filters["timeago"] = timeago


def ensure_voter_token(response: Response, voter_token: Optional[str]) -> str:
    if not voter_token:
        voter_token = str(uuid.uuid4())
        response.set_cookie(
            "voter_token",
            voter_token,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
        )
    return voter_token


def fetch_polls(
    db: Session,
    category: str = "",
    search: str = "",
    sort: str = "trending",
    limit: int = 30,
    offset: int = 0,
):
    query = db.query(Poll)
    if category:
        query = query.filter(Poll.category == category)
    if search:
        query = query.filter(Poll.title.ilike(f"%{search}%"))
    if sort == "closing_soon":
        query = query.filter(Poll.ends_at.isnot(None)).order_by(Poll.ends_at.asc())
    else:
        query = query.order_by(Poll.created_at.desc())
    polls = query.offset(offset).limit(limit).all()
    poll_ids = [p.id for p in polls]
    options_map: dict[int, list[PollOption]] = {p.id: [] for p in polls}
    if poll_ids:
        for opt in db.query(PollOption).filter(PollOption.poll_id.in_(poll_ids)).all():
            options_map[opt.poll_id].append(opt)
    if sort in ("trending", "most_voted"):
        def score(p: Poll):
            votes = sum(o.vote_count for o in options_map[p.id])
            if sort == "most_voted":
                return votes
            created = p.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_h = max((datetime.now(timezone.utc) - created).total_seconds() / 3600, 0.01)
            return votes / age_h
        polls = sorted(polls, key=score, reverse=True)
    return polls, options_map


def enrich_poll(poll: Poll, options: list[PollOption]) -> dict:
    total = sum(o.vote_count for o in options)
    options_data = sorted(
        [
            {
                "id": o.id,
                "text": o.text,
                "vote_count": o.vote_count,
                "percentage": round(o.vote_count / total * 100, 1) if total else 0.0,
            }
            for o in options
        ],
        key=lambda x: -x["vote_count"],
    )
    top = options_data[0] if options_data else None
    return {
        "id": poll.id,
        "title": poll.title,
        "description": poll.description,
        "category": poll.category,
        "created_at": poll.created_at,
        "ends_at": poll.ends_at,
        "total_votes": total,
        "is_active": is_active(poll),
        "creator_name": poll.creator_name,
        "options": options_data,
        "top_option": top,
    }


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    response: Response,
    category: str = "",
    search: str = "",
    sort: str = "trending",
    db: Session = Depends(get_db),
    voter_token: Optional[str] = Cookie(None),
):
    voter_token = ensure_voter_token(response, voter_token)
    polls, options_map = fetch_polls(db, category, search, sort, limit=30)
    enriched = [enrich_poll(p, options_map[p.id]) for p in polls]

    total_polls = db.query(func.count(Poll.id)).scalar() or 0
    total_votes = db.query(func.count(Vote.id)).scalar() or 0
    now = datetime.now(timezone.utc)
    active_polls = (
        db.query(func.count(Poll.id))
        .filter(Poll.is_active == True, or_(Poll.ends_at.is_(None), Poll.ends_at > now))
        .scalar()
        or 0
    )

    cats = (
        db.query(Poll.category, func.count(Poll.id).label("n"))
        .filter(Poll.category.isnot(None))
        .group_by(Poll.category)
        .order_by(func.count(Poll.id).desc())
        .all()
    )

    return templates.TemplateResponse(request, "index.html", {
        "polls": enriched,
        "total_polls": total_polls,
        "total_votes": total_votes,
        "active_polls": active_polls,
        "categories": cats,
        "current_category": category,
        "current_search": search,
        "current_sort": sort,
    })


@app.get("/partials/polls", response_class=HTMLResponse)
def partials_polls(
    request: Request,
    category: str = "",
    search: str = "",
    sort: str = "trending",
    db: Session = Depends(get_db),
):
    polls, options_map = fetch_polls(db, category, search, sort, limit=30)
    enriched = [enrich_poll(p, options_map[p.id]) for p in polls]
    return templates.TemplateResponse(request, "_polls_grid.html", {"polls": enriched})


@app.get("/poll/{poll_id}", response_class=HTMLResponse)
def poll_detail(
    poll_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    voter_token: Optional[str] = Cookie(None),
):
    voter_token = ensure_voter_token(response, voter_token)
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")

    options = db.query(PollOption).filter(PollOption.poll_id == poll_id).order_by(PollOption.id).all()
    vote = db.query(Vote).filter(Vote.poll_id == poll_id, Vote.voter_token == voter_token).first()
    user_voted_option_id = vote.option_id if vote else None

    data = enrich_poll(poll, options)
    return templates.TemplateResponse(request, "poll.html", {
        "poll": data,
        "poll_obj": poll,
        "user_voted_option_id": user_voted_option_id,
        "voter_token": voter_token,
    })


@app.post("/poll/{poll_id}/vote", response_class=HTMLResponse)
def vote(
    poll_id: int,
    request: Request,
    option_id: int = Form(...),
    db: Session = Depends(get_db),
    voter_token: Optional[str] = Cookie(None),
):
    if not voter_token:
        raise HTTPException(status_code=400, detail="No voter token")

    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll or not is_active(poll):
        raise HTTPException(status_code=400, detail="Poll not found or closed")

    if db.query(Vote).filter(Vote.poll_id == poll_id, Vote.voter_token == voter_token).first():
        raise HTTPException(status_code=400, detail="Already voted")

    option = db.query(PollOption).filter(PollOption.id == option_id, PollOption.poll_id == poll_id).first()
    if not option:
        raise HTTPException(status_code=400, detail="Invalid option")

    option.vote_count += 1
    db.add(Vote(poll_id=poll_id, option_id=option_id, voter_token=voter_token))
    db.commit()

    updated = db.query(PollOption).filter(PollOption.poll_id == poll_id).order_by(PollOption.id).all()
    data = enrich_poll(poll, updated)

    return templates.TemplateResponse(request, "_vote_results.html", {
        "poll": data,
        "user_voted_option_id": option_id,
    })


@app.get("/create", response_class=HTMLResponse)
def create_get(request: Request, response: Response, voter_token: Optional[str] = Cookie(None)):
    voter_token = ensure_voter_token(response, voter_token)
    return templates.TemplateResponse(request, "create.html", {"categories": CATEGORIES, "error": None})


@app.post("/create")
async def create_post(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form(""),
    creator_name: str = Form(""),
    ends_at: str = Form(""),
    option1: str = Form(...),
    option2: str = Form(...),
    option3: str = Form(""),
    option4: str = Form(""),
    option5: str = Form(""),
    option6: str = Form(""),
    db: Session = Depends(get_db),
):
    options = [o.strip() for o in [option1, option2, option3, option4, option5, option6] if o.strip()]
    if len(options) < 2:
        return templates.TemplateResponse(request, "create.html",
            {"categories": CATEGORIES, "error": "At least 2 options are required."},
            status_code=400,
        )

    ends_dt = None
    if ends_at:
        try:
            ends_dt = datetime.fromisoformat(ends_at).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    poll = Poll(
        title=title.strip(),
        description=description.strip() or None,
        category=category or None,
        creator_name=creator_name.strip() or None,
        ends_at=ends_dt,
    )
    db.add(poll)
    db.flush()
    for text in options:
        db.add(PollOption(poll_id=poll.id, text=text, vote_count=0))
    db.commit()
    return RedirectResponse(url=f"/poll/{poll.id}", status_code=303)


@app.get("/healthz")
def health():
    return {"status": "ok"}
