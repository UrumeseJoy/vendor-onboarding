# Demo script (about 5 minutes)

Order: **01 → 02 → 04 → resubmit with 05 → 06 → 07 → Dashboard.** Cases 03 and 08 are not in the video; they are in the README if asked.

## Before recording

1. Backend: `cd backend && source venv/bin/activate && uvicorn app.main:app --port 8000` (one process only).
2. Frontend: `cd frontend && npm run dev`, open http://localhost:5173.
3. Check the **extractor label** at the top right. It should say **Extractor: Gemini** (or **Mock** if you started in mock mode; see the backup plan).
4. In the left sidebar, under **Demo**, click **Reset demo → Yes, reset**. You land on the Dashboard with every count at 0. (`DEMO_MODE=true` must be set in `backend/.env`, or the Demo group is hidden.)
5. Go to **Submit**. Keep the sample picker open.

Case 07 needs case 01 to have run first, and case 05 needs case 04 first. Following the order below does this.

## Opening (20 seconds)

> "This is an automated vendor onboarding process. A vendor submits a form and documents; eight stages of checks run, and it returns approved, pending or rejected with every reason visible. AI reads the documents and drafts the emails, but it never makes the decision: that is plain, deterministic code, so the same input always gives the same answer."

## 1. Case 01, Clean vendor (about 40 s)

- **Click:** Submit → pick **01 Clean vendor** → **Run this sample**.
- **Show:** the stages finishing live, then the result: **APPROVED**, risk score 0, all checks passed. Open the documents panel to show what was read (account number shows only the last 4 digits).
- **Say:** "Everything is valid and consistent, so it is approved. Note every check is listed with its result, so a reviewer can see what was verified, not just the outcome. This vendor also sets up case 07 later."

## 2. Case 02, Bank account in someone else's name (about 40 s)

- **Click:** Submit → **02** → Run.
- **Show:** **REJECTED**; open the failed `BANK_NAME_MATCH` check and the vendor email.
- **Say:** "The cheque says the account holder is Ramesh Kumar, not the company. That is the classic payment-diversion pattern, so it is a hard fail and the vendor is rejected. The name score is 37 against a pass mark of 90. Notice the email is a fixed neutral template: we never tell a rejected vendor why, and AI never writes it."

## 3. Case 04, Wrong document (about 50 s)

- **Click:** Submit → **04** → Run.
- **Show:** **PENDING**; the `DOC_TYPE_MATCH` failure and the vendor email. Click **Edit** on the email to show it can be changed, then **Approve & mark as sent**.
- **Say:** "The vendor uploaded an invoice in the GST certificate slot. The system reads what the document actually is, not what the vendor claims, and asks for the exact document needed. This is pending, not rejected, because it is fixable. A person approves the email before it goes out; here approving only marks it as sent."

## 4. Resubmit with case 05 (about 40 s)

- **Click:** on the result page, **Resubmit for this vendor** → pick **05 Vendor fixes and resubmits** → Run.
- **Show:** **APPROVED** on the same vendor ID. Open the vendor detail page to show both runs in the history.
- **Say:** "The vendor sends the correct certificate and the whole process re-runs on the same vendor ID. It is now approved, and both runs are kept, so there is a full audit trail of how it got there."

## 5. Case 06, Blurry scan (about 50 s)

- **Click:** Submit → **06** → Run.
- **Show:** **PENDING**; the `EXTRACTION_CONFIDENCE` failure and its message about the cheque.
- **Say:** "The cheque scan is too blurry. The system never guesses or trusts data it could not read; it asks for a clearer copy. In the real Gemini run the model was even more careful: it left the IFSC out entirely rather than guess. A confidence score alone would have missed that, so we also define which fields must be readable on each document type."

## 6. Case 07, Duplicate bank account (about 40 s)

- **Click:** Submit → **07** → Run.
- **Show:** **REJECTED**; the `DUPLICATE_BANK_ACCOUNT` check naming the other vendor, with the account shown as `••••5678`.
- **Say:** "A new vendor with a different name is using the same bank account as Sharma Electronics from the first case. That is a hard flag. We find it without storing account numbers: we keep a keyed fingerprint, so even our database cannot reveal an account number."

## 7. Dashboard (about 20 s)

- **Click:** Dashboard.
- **Show:** the counts by status and the vendor list. Open one vendor if there is time.
- **Say:** "Every vendor, every run and every decision is here, and any of them can be explained from its stored checks."

## Closing (20 seconds)

> "What I'd build next: penny-drop bank verification and a GSTN lookup so we verify against the source, sanctions screening, email intake so vendors don't need a form, and for production, Postgres, persistent file storage, a Redis event bus for multiple workers, and authentication."

## Backup plan: Gemini is slow or out of quota

The free Gemini tier is limited (roughly 20 requests per model per day), and a sample case should normally come from the committed pre-read cache without any API call. If a run still hangs, errors, or the extractor label shows a problem:

1. Stop the backend (Ctrl+C).
2. In `backend/.env` set `EXTRACTOR_MODE=mock`.
3. Restart: `uvicorn app.main:app --port 8000`.
4. Reload the page. The label at the top right now says **Extractor: Mock**.
5. **Reset demo** (sidebar) and start again from case 01.

Mock mode reads the same sample PDFs offline, so all 8 cases give the expected statuses. One visible difference: in case 06 the message says it couldn't clearly read the account number, IFSC and bank name, instead of the IFSC alone. Uploads of your own documents need Gemini, so keep to the sample cases in mock mode.
