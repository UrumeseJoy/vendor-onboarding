# Vendor Onboarding Automation

An automated vendor onboarding process built for the Zamp AI Solutions Analyst case study (PS-2). It takes a vendor submission (form fields plus uploaded PDF documents), runs it through an 8-stage pipeline of deterministic checks, and returns APPROVED, PENDING or REJECTED with every reason visible. Gemini is used only to extract document fields, classify documents and draft vendor emails — it never makes the decision. For anything not approved, a message to the vendor is drafted saying exactly what to fix.

## How to run

You need Python 3.11+ and Node 20+. Run the backend and the frontend in two terminals.

**Backend** (must run as a single process):

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit .env: set GEMINI_API_KEY, ACCOUNT_HASH_KEY, EXTRACTOR_MODE
uvicorn app.main:app --port 8000
```

- `EXTRACTOR_MODE=mock` reads the sample PDFs offline (no API key needed); `gemini` reads documents live.
- `DEMO_MODE=true` enables the "Reset demo" button on the Dashboard.
- Tests: `python -m pytest`. All 8 demo cases: `python -m scripts.run_case --all` (expects 8 of 8 matching).

**Frontend:**

```bash
cd frontend
npm install
cp .env.example .env        # VITE_API_URL=http://localhost:8000
npm run dev                 # http://localhost:5173
```

Checks: `npm run build` and `npm run lint`.

**Pages:** Submit (upload your own PDFs or run a sample case), Live run and Result (stages stream in as they
finish; the vendor email can be edited and approved), Dashboard (all vendors, counts, Reset demo) and
Vendor detail (run history and Resubmit). Approving an email only marks it as sent; nothing is actually emailed.

## Document reading and the demo cache

Documents are read by Gemini (`EXTRACTOR_MODE=gemini` in `backend/.env`; `mock` reads the sample PDFs
offline). The sample documents are **pre-read**: `backend/sample_data/extraction_cache/` is committed, so the
demo does not depend on API quota or latency. Any newly uploaded document is read by Gemini live.

- `python -m scripts.check_gemini` — which model is fast, reliable and has quota right now.
- `python -m scripts.eval_extraction` — accuracy of the reader on the sample PDFs.
- `python -m scripts.eval_extraction --save-seed` — rebuild the committed cache. Needed after changing
  `GEMINI_MODEL` or the prompt version. The free Gemini tier allows roughly 20 requests per model per day,
  and the 23 sample documents (21 distinct files) need about that many.

