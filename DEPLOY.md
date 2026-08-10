# Deploying Research Crew for free

Three services, all with permanent free tiers and no credit card required:

| Service | Role | Why this one |
|---|---|---|
| [Neon](https://neon.tech) | Postgres | Permanent free tier (unlike Render's, which expires after 90 days) |
| [Render](https://render.com) | Backend (FastAPI + LangGraph) | Free Docker web service; deploys straight from this repo's `Dockerfile` |
| [Vercel](https://vercel.com) | Frontend (React/Vite) | Free static hosting, zero-config for Vite |

**Known tradeoffs of the free tier** (not bugs — inherent to $0 hosting):
- Render's free web service sleeps after 15 minutes idle; the next request takes 30-60s to wake it. A long-running agent task in progress when it sleeps will be interrupted.
- Neon's free compute scales to zero after 5 minutes idle too — first query after that has a brief cold start, but your data itself never expires.
- Hosting is free; *using* it isn't — you still need your own `ANTHROPIC_API_KEY`, billed by Anthropic.

Deploy in this order — each step needs a value produced by the previous one.

## 1. Neon (Postgres)

1. Sign up at [neon.tech](https://neon.tech) (GitHub login is fastest, no card needed).
2. Create a project (any name/region).
3. From the project dashboard, copy the **connection string** (starts with `postgresql://...?sslmode=require`). Keep it handy for step 2.

## 2. Render (backend)

1. Sign up at [render.com](https://render.com) (no card needed for free services).
2. **New → Blueprint**, connect your GitHub account, select this repo (`research-crew`).
3. Render detects `render.yaml` at the repo root and shows the `research-crew-backend` service. Click through — it'll prompt for the env vars marked `sync: false`:
   - `DATABASE_URL` → the Neon connection string from step 1
   - `ANTHROPIC_API_KEY` → your Anthropic API key
   - `CORS_ORIGINS` → leave as `http://localhost:5173` for now; you'll update this after step 3
4. Deploy. Once it's live, copy the service URL (e.g. `https://research-crew-backend.onrender.com`).
5. On the service's **Environment** tab, copy the auto-generated `API_DEV_KEY` value — you'll need it in step 3.

## 3. Vercel (frontend)

1. Sign up at [vercel.com](https://vercel.com) (no card needed for Hobby).
2. **Add New → Project**, import the same GitHub repo.
3. Set **Root Directory** to `frontend` (Vercel auto-detects the Vite framework preset once you do).
4. Add two environment variables:
   - `VITE_API_BASE_URL` → your Render backend URL from step 2 (no trailing slash)
   - `VITE_API_DEV_KEY` → the `API_DEV_KEY` value you copied from Render
5. Deploy. Copy the resulting URL (e.g. `https://research-crew.vercel.app`).

## 4. Close the loop: update CORS

Go back to the Render service's **Environment** tab and set `CORS_ORIGINS` to your Vercel URL from step 3 (e.g. `https://research-crew.vercel.app`), then trigger a redeploy (Render does this automatically on env var changes for most plans; if not, click **Manual Deploy**).

## 5. Verify

Visit your Vercel URL, start a run, and watch it stream. First request may take 30-60s if Render's free instance was asleep — that's expected.
