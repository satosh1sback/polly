# Workspace

## Overview

Pulse — a Polymarket-inspired opinion polling platform where anyone can create polls on any topic and vote freely (no money). Built as a pure Python stack with server-side rendering.

## Stack

- **Backend**: FastAPI (Python 3.11) + Uvicorn
- **Templates**: Jinja2 (server-side HTML rendering)
- **Frontend interaction**: HTMX (live search/filter/vote, no page reloads)
- **Styling**: Tailwind CSS (via CDN)
- **Database**: PostgreSQL + SQLAlchemy ORM
- **Voter tracking**: Browser cookie (`voter_token`, anonymous UUID)

## File Structure

The entire app lives in `artifacts/api-server-python/`:

```
artifacts/api-server-python/
├── main.py          # All FastAPI routes and request handlers
├── database.py      # SQLAlchemy DB connection setup
├── models.py        # Database table definitions (Poll, PollOption, Vote)
├── run.py           # Server startup script (reads PORT env var)
├── requirements.txt # Python package dependencies
└── templates/
    ├── base.html         # Shared page shell (navbar, footer, CDN scripts)
    ├── index.html        # Explore/home page with HTMX filters
    ├── poll.html         # Poll detail with vote buttons
    ├── create.html       # Create poll form
    ├── _polls_grid.html  # HTMX partial: poll cards grid
    └── _vote_results.html # HTMX partial: vote result bars
```

See `STRUCTURE.txt` at the root for a full plain-English guide to every file.

## Pages / Routes

- `GET /` — Explore page (all polls, search, category filter, sort)
- `GET /poll/{id}` — Poll detail with voting
- `POST /poll/{id}/vote` — Cast vote (returns HTMX partial with updated bars)
- `GET /create` — Create poll form
- `POST /create` — Submit new poll, redirects to poll page
- `GET /partials/polls` — HTMX partial: filtered polls grid
- `GET /healthz` — Health check

## Database Schema

- `polls` — poll question, description, category, creator name, end date, active flag
- `poll_options` — answer options with vote counts
- `votes` — one row per vote, keyed by voter_token cookie (anonymous)

## How Voting Works

On first page visit, a UUID cookie `voter_token` is set. When a user votes, the
cookie is sent automatically. The server checks for an existing vote by that token
and rejects duplicates. The response is an HTML fragment (HTMX swaps it in-place).

## Running Locally

The workflow `artifacts/polls: web` runs:
```
cd /home/runner/workspace/artifacts/api-server-python && PORT=23969 python run.py
```

## Artifacts

- `artifacts/polls` — Main Pulse app (Python/FastAPI, served at `/`)
- `artifacts/api-server` — Old Node.js server (inactive, kept for reference)
- `artifacts/mockup-sandbox` — Design canvas tool (dev only)
