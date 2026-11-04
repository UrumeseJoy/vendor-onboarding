"""Generate synthetic test PDFs for every sample case.

Run from the backend folder:
    python -m scripts.generate_documents              # all cases
    python -m scripts.generate_documents 01_happy_path  # one case
    python -m scripts.generate_documents --previews   # also write PNG previews

Each documents.json entry becomes one PDF in sample_data/cases/<case>/files/.
All documents are marked SPECIMEN and carry no real logos or emblems.
"""

import argparse
import json
import math
import re
from io import BytesIO
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from app.config import state_name_for_gst_code

SAMPLE_DIR = Path(__file__).parent.parent / "sample_data"
CASES_DIR = SAMPLE_DIR / "cases"
PREVIEW_DIR = SAMPLE_DIR / "previews"

# (case_id, filename) pairs rendered as PNG previews with --previews
PREVIEWS = [
    ("01_happy_path", "gst_certificate.pdf"),
    ("01_happy_path", "cancelled_cheque.pdf"),
    ("04_wrong_document", "gst_certificate.pdf"),
    ("06_blurry_scan", "cancelled_cheque.pdf"),
    ("08_us_vendor", "w9_form.pdf"),
]

BLUR_SEED = 42


# ---------- Small drawing helpers ----------

def new_page(size=A4):
    """Start an in-memory PDF. invariant=1 keeps the bytes identical on every run."""
    buf = BytesIO()
    return buf, canvas.Canvas(buf, pagesize=size, invariant=1)


def watermark(c, w, h):
    """Light grey diagonal watermark, drawn last and semi-transparent so values stay readable."""
    c.saveState()
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.setFillAlpha(0.18)
    c.setFont("Helvetica-Bold", 26)
    c.translate(w / 2, h / 2)
    c.rotate(math.degrees(math.atan2(h, w)))
    c.drawCentredString(0, 0, "SPECIMEN — SYNTHETIC TEST DOCUMENT")
    c.restoreState()


def rows(c, x, y, items, label_w=150, value_w=330, gap=8):
    """Draw 'Label   Value' rows (value wraps if long). Returns the y below the last row."""
    for label, value in items:
        lines = simpleSplit(str(value), "Helvetica-Bold", 11, value_w)
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.35, 0.35, 0.35)
        c.drawString(x, y, label)
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0, 0, 0)
        for line in lines:
            c.drawString(x + label_w, y, line)
            y -= 14
        y -= gap
    return y


def money(amount: float) -> str:
    return f"INR {amount:,.2f}"


# ---------- One template per document type ----------

def gst_certificate(f):
    buf, c = new_page()
    w, h = A4
    c.setLineWidth(1.5)
    c.rect(30, 30, w - 60, h - 60)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, h - 80, "Certificate of Registration (Form GST REG-06) — SPECIMEN")
    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, h - 98, "Goods and Services Tax — sample layout for testing only")
    c.line(50, h - 112, w - 50, h - 112)
    state = state_name_for_gst_code(f.get("gstin", "")[:2]) or "—"
    rows(c, 60, h - 145, [
        ("1. Registration Number (GSTIN)", f.get("gstin", "")),
        ("2. Legal Name", f.get("legal_name", "")),
        ("3. Trade Name", f.get("legal_name", "")),
        ("4. Constitution of Business", "Private Limited Company"),
        ("5. Address of Principal Place of Business", f.get("address", "")),
        ("6. State", state),
        ("7. PAN", f.get("pan", "")),
        ("8. Date of Liability", "01/04/2020"),
        ("9. Type of Registration", "Regular"),
    ], label_w=210, value_w=280)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(60, 70, "This is a computer-generated specimen. Not valid for any official purpose.")
    watermark(c, w, h)
    c.save()
    return buf.getvalue()


def pan_card(f):
    buf, c = new_page()
    w, h = A4
    cw, ch = 86 * mm, 54 * mm
    x, y = (w - cw) / 2, (h - ch) / 2 + 60
    c.setFillColorRGB(0.88, 0.93, 0.98)
    c.setLineWidth(1)
    c.roundRect(x, y, cw, ch, 6, fill=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 10, y + ch - 16, "Permanent Account Number — SPECIMEN")
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.drawString(x + 10, y + ch - 42, "PAN")
    c.drawString(x + 10, y + ch - 78, "Name of entity")
    c.drawString(x + 10, y + ch - 114, "Date of incorporation")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x + 10, y + ch - 56, f.get("pan", ""))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 10, y + ch - 90, f.get("legal_name", ""))
    c.drawString(x + 10, y + ch - 126, "12/04/2015")
    watermark(c, w, h)
    c.save()
    return buf.getvalue()


def cancelled_cheque(f):
    size = landscape(A4)
    buf, c = new_page(size)
    w, h = size
    cw, ch = 203 * mm, 92 * mm
    x, y = (w - cw) / 2, (h - ch) / 2
    c.setFillColorRGB(0.95, 0.97, 0.92)
    c.setLineWidth(1)
    c.rect(x, y, cw, ch, fill=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x + 15, y + ch - 28, f.get("bank_name", ""))
    c.setFont("Helvetica", 9)
    c.drawString(x + 15, y + ch - 42, "Main Branch")
    c.drawRightString(x + cw - 15, y + ch - 28, f"IFSC: {f.get('ifsc', '')}")
    c.drawRightString(x + cw - 15, y + ch - 42, "DATE  __ __ / __ __ / __ __ __ __")
    c.drawString(x + 15, y + ch - 75, "Pay")
    c.line(x + 40, y + ch - 77, x + cw - 15, y + ch - 77)
    c.drawString(x + 15, y + ch - 105, "Rupees")
    c.line(x + 50, y + ch - 107, x + cw - 150, y + ch - 107)
    c.rect(x + cw - 140, y + ch - 115, 125, 22)
    c.setFont("Helvetica", 9)
    c.drawString(x + 15, y + 62, "A/c Holder Name:")
    c.drawString(x + 15, y + 42, "A/c No.:")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x + 105, y + 62, f.get("holder_name", ""))
    c.drawString(x + 105, y + 42, f.get("account_number", ""))
    c.setFont("Helvetica", 8)
    c.drawRightString(x + cw - 15, y + 22, "Authorised Signatory")
    c.line(x + cw - 160, y + 32, x + cw - 15, y + 32)
    # CANCELLED stamp
    c.saveState()
    c.setStrokeColorRGB(0.8, 0.1, 0.1)
    c.setFillColorRGB(0.8, 0.1, 0.1)
    c.setStrokeAlpha(0.45)
    c.setFillAlpha(0.45)
    c.translate(x + cw / 2, y + ch / 2 + 30)
    c.rotate(20)
    c.setLineWidth(3)
    c.rect(-150, -30, 300, 60)
    c.setFont("Helvetica-Bold", 48)
    c.drawCentredString(0, -17, "CANCELLED")
    c.restoreState()
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(w / 2, y + ch + 20, "Specimen cancelled cheque — SPECIMEN")
    watermark(c, w, h)
    c.save()
    return buf.getvalue()


def bank_letter(f):
    buf, c = new_page()
    w, h = A4
    bank = f.get("bank_name", "")
    c.setFillColorRGB(0.12, 0.25, 0.45)
    c.rect(0, h - 90, w, 90, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, h - 50, bank)
    c.setFont("Helvetica", 9)
    c.drawString(50, h - 68, "Corporate Banking Services — Account Verification Desk")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 10)
    c.drawString(50, h - 130, "Date: 15 October 2026")
    c.drawString(50, h - 160, "To Whom It May Concern")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, h - 190, "Re: Bank account confirmation letter — SPECIMEN")
    c.setFont("Helvetica", 10)
    c.drawString(50, h - 220, "We confirm that the following account is held with us:")
    routing = f.get("routing_number")
    id_label, id_value = ("Routing Number", routing) if routing else ("IFSC", f.get("ifsc", ""))
    y = rows(c, 70, h - 255, [
        ("Account Holder", f.get("holder_name", "")),
        ("Account Number", f.get("account_number", "")),
        (id_label, id_value),
        ("Bank Name", bank),
        ("Account Status", "Active"),
    ], label_w=130, value_w=330)
    c.setFont("Helvetica", 10)
    c.drawString(50, y - 10, "This account is active and in good standing. This letter is issued at the")
    c.drawString(50, y - 24, "request of the account holder.")
    c.drawString(50, y - 70, "Yours sincerely,")
    c.drawString(50, y - 110, "Authorised Signatory")
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, y - 124, bank)
    watermark(c, w, h)
    c.save()
    return buf.getvalue()


def w9_form(f):
    buf, c = new_page()
    w, h = A4
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, h - 55, "Form W-9 (simplified specimen) — Request for Taxpayer Identification Number")
    c.setFont("Helvetica", 9)
    c.drawString(40, h - 72, "Give this form to the requester. Do not send to the IRS. (Synthetic layout for testing)")
    c.setLineWidth(1)
    c.rect(40, h - 400, w - 80, 310)
    y = h - 115
    for label, value in [
        ("1  Name (as shown on your income tax return)", f.get("legal_name", "")),
        ("2  Business name / disregarded entity name", f.get("legal_name", "")),
        ("3  Federal tax classification", "[X] Limited liability company (LLC)    [ ] C Corp   [ ] S Corp   [ ] Partnership"),
        ("5  Address (number, street, city, state, ZIP)", f.get("address", "")),
    ]:
        c.setFont("Helvetica", 8)
        c.setFillColorRGB(0.35, 0.35, 0.35)
        c.drawString(50, y, label)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 10)
        for line in simpleSplit(value, "Helvetica-Bold", 10, w - 120):
            y -= 16
            c.drawString(60, y, line)
        y -= 14
        c.line(50, y + 8, w - 50, y + 8)
    y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Part I — Taxpayer Identification Number (TIN)")
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.drawString(50, y - 20, "Employer identification number (EIN)")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(60, y - 40, f.get("ein", ""))
    c.setFont("Helvetica", 8)
    c.drawString(50, y - 75, "Part II — Certification: Under penalties of perjury, I certify the information on this form is correct.")
    c.drawString(50, y - 100, "Signature of U.S. person: ______________________      Date: ____ / ____ / ________")
    watermark(c, w, h)
    c.save()
    return buf.getvalue()


# Fixed seller on the sample invoice (fictional; the GSTIN checksum is correct)
SELLER_NAME = "Greenfield Supplies Private Limited"
SELLER_GSTIN = "33AABCG4321H1Z4"


def invoice(f):
    buf, c = new_page()
    w, h = A4
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, h - 60, "TAX INVOICE — SPECIMEN")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, h - 90, f.get("seller_name", SELLER_NAME))
    c.setFont("Helvetica", 9)
    c.drawString(50, h - 104, f"GSTIN: {f.get('seller_gstin', SELLER_GSTIN)}")
    rows(c, 50, h - 140, [
        ("Invoice Number", f.get("invoice_number", "")),
        ("Invoice Date", f.get("invoice_date", "")),
        ("Bill To (Buyer)", f.get("buyer_name", "")),
    ], label_w=110, value_w=350, gap=4)

    total = float(re.sub(r"[^\d.]", "", f.get("total_amount", "0")) or 0)
    subtotal = round(total / 1.18, 2)
    gst = round(total - subtotal, 2)
    a1, a2 = round(subtotal * 0.6, 2), round(subtotal * 0.25, 2)
    items = [("Industrial packaging cartons", 6, a1 / 6), ("Printed product labels", 5, a2 / 5),
             ("Handling and delivery", 1, round(subtotal - a1 - a2, 2))]
    y = h - 270
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y, "Description")
    c.drawRightString(350, y, "Qty")
    c.drawRightString(440, y, "Rate")
    c.drawRightString(545, y, "Amount")
    c.line(50, y - 5, 545, y - 5)
    c.setFont("Helvetica", 9)
    for desc, qty, rate in items:
        y -= 20
        c.drawString(50, y, desc)
        c.drawRightString(350, y, str(qty))
        c.drawRightString(440, y, f"{rate:,.2f}")
        c.drawRightString(545, y, f"{qty * rate:,.2f}")
    y -= 15
    c.line(50, y, 545, y)
    for label, value, bold in [("Subtotal", subtotal, False), ("GST @ 18%", gst, False), ("Total", total, True)]:
        y -= 18
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        c.drawString(360, y, label)
        c.drawRightString(545, y, money(value))
    watermark(c, w, h)
    c.save()
    return buf.getvalue()


TEMPLATES = {
    "GST_CERTIFICATE": gst_certificate,
    "PAN_CARD": pan_card,
    "CANCELLED_CHEQUE": cancelled_cheque,
    "BANK_LETTER": bank_letter,
    "W9_FORM": w9_form,
    "INVOICE": invoice,
}


# ---------- Blurry scan ----------

def make_blurry(clean_pdf: bytes) -> bytes:
    """Rasterise page 1, degrade it, and return an image-only PDF (no text layer).
    Fixed seed, so the output is identical on every run."""
    src = pymupdf.open(stream=clean_pdf, filetype="pdf")
    page = src[0]
    pix = page.get_pixmap(dpi=110)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    img = img.filter(ImageFilter.GaussianBlur(radius=2.2))
    img = img.rotate(2.0, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    img = ImageEnhance.Contrast(img).enhance(0.6)
    rng = np.random.default_rng(BLUR_SEED)
    noise = rng.normal(0, 10, (img.height, img.width, 1))
    img = Image.fromarray(np.clip(np.asarray(img) + noise, 0, 255).astype("uint8"))

    jpeg = BytesIO()
    img.save(jpeg, format="JPEG", quality=70)
    out = pymupdf.open()
    new = out.new_page(width=page.rect.width, height=page.rect.height)
    new.insert_image(new.rect, stream=jpeg.getvalue())
    out.set_metadata({})
    return out.tobytes(no_new_id=True)


# ---------- Driver ----------

def generate_case(case_id: str) -> None:
    case_dir = CASES_DIR / case_id
    files_dir = case_dir / "files"
    files_dir.mkdir(exist_ok=True)
    for entry in json.loads((case_dir / "documents.json").read_text()):
        pdf = TEMPLATES[entry["actual_type"]](entry["fields"])
        if entry["quality"] == "blurry_scan":
            pdf = make_blurry(pdf)
        (files_dir / entry["filename"]).write_bytes(pdf)
        print(f"{case_id}/files/{entry['filename']}  ({entry['actual_type']}, {entry['quality']})")


def render_previews() -> None:
    PREVIEW_DIR.mkdir(exist_ok=True)
    for case_id, filename in PREVIEWS:
        doc = pymupdf.open(CASES_DIR / case_id / "files" / filename)
        out = PREVIEW_DIR / f"{case_id}__{Path(filename).stem}.png"
        doc[0].get_pixmap(dpi=90).save(out)
        print(f"preview: {out.relative_to(SAMPLE_DIR.parent)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("case_id", nargs="?", help="regenerate just this case")
    parser.add_argument("--previews", action="store_true", help="also write PNG previews")
    args = parser.parse_args()
    case_ids = [args.case_id] if args.case_id else sorted(p.name for p in CASES_DIR.iterdir() if p.is_dir())
    for case_id in case_ids:
        generate_case(case_id)
    if args.previews:
        render_previews()


if __name__ == "__main__":
    main()
