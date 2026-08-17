# Deploying Research Crew on Vercel

Two services, both permanent free tiers, no credit card required:

| Service | Role | Why this one |
|---|---|---|
| [Neon](https://neon.tech) | Postgres (checkpointer + run store) | Permanent free tier; provisioned automatically through the Vercel Marketplace |
| [Vercel](https://vercel.com) | Frontend (Vite) + backend (FastAPI, Python runtime) | One platform for both — Vercel's Python runtime runs FastAPI directly, no Docker needed |

**Known tradeoffs of the free tier** (not bugs — inherent to $0 hosting):
- Neon's free compute scales to zero after 5 minutes idle — first query after that has a
  brief cold start, but data never expires.
- Vercel Functions have a duration cap (`maxDuration: 60` is set on the backend here) — a
  very long agent run could be cut off. Raise it on a paid plan if that matters to you.
- Hosting is free; *using* it isn't — you still need your own `ANTHROPIC_API_KEY`, billed by
  Anthropic, and optionally `TAVILY_API_KEY` for the researcher agent's web search.

## 1. Provision Postgres

From `backend/`, with the Vercel CLI authenticated and the project linked:

```bash
vercel link --yes --project research-crew-backend
vercel integration add neon   # accept marketplace terms in the browser the first time
```

This injects `DATABASE_URL` automatically. `AsyncPostgresSaver.setup()` creates the
checkpoint tables idempotently on every cold start — no manual migration step.

## 2. Deploy the backend

```bash
vercel env add ANTHROPIC_API_KEY production   # required — agent runs fail without it
vercel env add TAVILY_API_KEY production      # optional — researcher agent's web search
vercel env add CORS_ORIGINS production        # your frontend URL, from step 3
vercel env add API_DEV_KEY production         # any random string; the frontend needs the same value
vercel env add WORKSPACES_DIR production      # set to /tmp/workspaces — Vercel's filesystem is read-only except /tmp
vercel --prod --yes
```

Vercel auto-detects `pyproject.toml` and installs with `uv` — no `requirements.txt` needed
(one's kept in this repo anyway as a fallback, but Vercel's own build log shows it using
`uv` directly).

## 3. Deploy the frontend

```bash
cd ../frontend
vercel link --yes --project research-crew-frontend
vercel env add VITE_API_BASE_URL production   # the backend URL from step 2
vercel env add VITE_API_DEV_KEY production    # same value as API_DEV_KEY above
vercel --prod --yes
```

## 4. Close the loop: update CORS

Go back to the backend project and set `CORS_ORIGINS` to the frontend URL from step 3, then
redeploy (`vercel --prod --yes` from `backend/`).

## Verify

```bash
curl https://<your-backend>.vercel.app/health   # {"status":"ok"}
```

Visit the frontend URL and start a run. If `ANTHROPIC_API_KEY` isn't set yet, the app loads
fine but runs will fail — that's the one piece that can't be automated, since it's your own
billed API key.
