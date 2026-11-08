# Deploying

Backend on **Render**, frontend on **Vercel**, database on any **Postgres** (Render, Neon, Supabase). About 20 minutes the first time.

The order matters: backend first (so you have its URL), then frontend, then tell the backend the frontend's URL.

## 0. Before you start

1. Push this repo to GitHub (the `.env` file is git-ignored; never commit it).
2. Create a Postgres database and copy its **connection string** (it starts with `postgres://` or `postgresql://`; both work).
3. Generate two secrets. Run this twice and keep the two outputs:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

   - first value: `ACCOUNT_HASH_KEY` (keys the bank-account fingerprints; **do not change it later**, or old duplicates will no longer be recognised)
   - second value: `ADMIN_TOKEN` (the password for the Reset demo button)

## 1. Render (backend)

1. Go to https://dashboard.render.com and sign in with GitHub.
2. Click **New +** → **Blueprint**.
3. Pick this repository. Render reads `render.yaml` and shows one service, `vendor-onboarding-api` (free plan, Singapore). Click **Apply**.
4. When asked for the secret values, fill in:

   | Name | Value |
   |---|---|
   | `GEMINI_API_KEY` | your Gemini API key |
   | `DATABASE_URL` | the Postgres connection string |
   | `ACCOUNT_HASH_KEY` | the first generated secret |
   | `ADMIN_TOKEN` | the second generated secret |
   | `FRONTEND_ORIGINS` | leave a placeholder such as `https://example.com` for now; set it properly in step 3 |

   The other settings (`EXTRACTOR_MODE=gemini`, `GEMINI_MODEL`, `DEMO_MODE=true`, `STAGE_DELAY_MS=400`, `PYTHON_VERSION=3.14.6`) are already in `render.yaml`.
5. Wait for the first deploy to finish (a few minutes). Open the service and copy its URL, like `https://vendor-onboarding-api.onrender.com`.
6. Check it: open `<that URL>/api/health`. You should see `"status":"ok"`.

If the deploy log says the database is not reachable, the `DATABASE_URL` is wrong. The log names the problem without printing the URL.

## 2. Vercel (frontend)

1. Go to https://vercel.com and sign in with GitHub.
2. Click **Add New…** → **Project**, and import the same repository.
3. Set **Root Directory** to `frontend` (click **Edit** next to it). Vercel detects Vite; leave the build settings alone.
4. Open **Environment Variables** and add:

   | Name | Value |
   |---|---|
   | `VITE_API_URL` | the Render URL from step 1, with no trailing slash |

5. Click **Deploy**. When it finishes, copy the site URL, like `https://your-app.vercel.app`.

`frontend/vercel.json` makes links such as `/runs/...`, `/vendors/...` and `/submit` open correctly when pasted or refreshed.

## 3. Tell the backend where the frontend is, and redeploy

1. Back in Render, open the service → **Environment**.
2. Set `FRONTEND_ORIGINS` to the Vercel URL (no trailing slash, e.g. `https://your-app.vercel.app`). Several URLs can be separated by commas.
3. Click **Save changes**. Render redeploys automatically; if it does not, use **Manual Deploy** → **Deploy latest commit**.
4. Open the Vercel site. The extractor label at the top right should say **Extractor: Gemini**.

If the page loads but shows "Can't reach the backend", `VITE_API_URL` or `FRONTEND_ORIGINS` is wrong (a trailing slash or `http` instead of `https` is the usual cause). After changing a Vercel variable, redeploy the frontend.

## Using it

- **Reset demo** (sidebar → Demo) asks for the `ADMIN_TOKEN`. The browser remembers it only until the tab is closed.
- **Free Render service sleeps when idle.** The first visit after a quiet spell takes about a minute to wake. Open the site a couple of minutes before a demo.
- **Uploaded PDFs are lost on every redeploy or restart** (the free plan's disk is temporary). The run page then shows "Document no longer available" for them. The sample documents always work, because they are part of the repository.
- The backend must stay a single process (`--workers 1` is already set).

## Environment variable names

**Render:** `GEMINI_API_KEY`, `DATABASE_URL`, `ACCOUNT_HASH_KEY`, `ADMIN_TOKEN`, `FRONTEND_ORIGINS` (set by you); `PYTHON_VERSION`, `GEMINI_MODEL`, `EXTRACTOR_MODE`, `DEMO_MODE`, `STAGE_DELAY_MS` (already in `render.yaml`).

**Vercel:** `VITE_API_URL`.
