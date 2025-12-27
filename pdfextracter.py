import json
import re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

import pdfplumber


# --- keyword + amount parsing ---

KEYWORDS = [
    "überweisung", "ueberweisung", "zahlungen",
    "auszahlungsbetrag", "auszahlung", "ausgezahlt", "netto",
    "paid out", "payout", "net pay",
]

# Matches: 1.024,09  OR 1024,09  (optional € / EUR afterwards is fine)
AMOUNT_RE = re.compile(r"(\d+(?:\.\d{3})*,\d{2})")

@dataclass
class Payout:
    file: str
    amount: float
    raw_amount: str
    matched_line: str

def de_amount_to_float(s: str) -> float:
    # "1.024,09" -> 1024.09
    return float(s.replace(".", "").replace(",", "."))

def normalize(s: str) -> str:
    # Helps match Überweisung even if extracted as Ueberweisung, etc.
    s = s.lower()
    s = (s.replace("ü", "ue")
           .replace("ö", "oe")
           .replace("ä", "ae")
           .replace("ß", "ss"))
    return s

def extract_pdf_text(pdf_path: Path) -> str:
    chunks = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            chunks.append(page.extract_text() or "")
    return "\n".join(chunks)

def find_payout_amount(text: str) -> Optional[Payout]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    norm = [normalize(ln) for ln in lines]

    candidates: list[tuple[int, float, str, str]] = []
    # (score, amount_float, raw_amount, matched_line)

    def add_candidate(score: int, ln: str):
        m = AMOUNT_RE.search(ln)
        if not m:
            return
        raw = m.group(1)
        amt = de_amount_to_float(raw)
        candidates.append((score, amt, raw, ln))

    # 1) Strongest signal: inside/near the "Zahlungen" block, line with "Überweisung"
    for i, nln in enumerate(norm):
        if "zahlungen" in nln:
            # scan the next ~20 lines after "Zahlungen"
            for j in range(i, min(i + 20, len(lines))):
                n2 = norm[j]
                ln2 = lines[j]

                if "ueberweisung" in n2 or "überweisung" in ln2.lower():
                    score = 100
                    if "eur" in n2 or "€" in ln2:
                        score += 20
                    add_candidate(score, ln2)

                    # sometimes amount can be on the next line
                    if j + 1 < len(lines):
                        add_candidate(score - 5, lines[j + 1])

    # 2) Next best: explicit payout words anywhere
    payout_words = ["auszahlungsbetrag", "netto", "auszahlung", "ausgezahlt"]
    for i, nln in enumerate(norm):
        if any(w in nln for w in payout_words):
            score = 80
            if "eur" in nln or "€" in lines[i]:
                score += 10
            add_candidate(score, lines[i])
            if i + 1 < len(lines):
                add_candidate(score - 5, lines[i + 1])

    # 3) Weaker: any "Überweisung" line anywhere (could be extra payments)
    for i, nln in enumerate(norm):
        if "ueberweisung" in nln or "überweisung" in lines[i].lower():
            score = 40
            if "eur" in nln or "€" in lines[i]:
                score += 10
            add_candidate(score, lines[i])

    if not candidates:
        return None

    # Pick best by score, then by highest amount (if tie)
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best_score, best_amt, best_raw, best_line = candidates[0]

    return Payout(file="", amount=best_amt, raw_amount=best_raw, matched_line=best_line)



# --- choosing the newest PDF by YYYYMM in filename ---

YEAR_MONTH_RE = re.compile(r"(20\d{2})(0[1-9]|1[0-2])")  # 202401..202512

def extract_yyyymm_from_name(name: str) -> Optional[datetime]:
    m = YEAR_MONTH_RE.search(name)
    if not m:
        return None
    ym = m.group(1) + m.group(2)  # "202512"
    try:
        return datetime.strptime(ym, "%Y%m")
    except ValueError:
        return None

def get_folder_from_save() -> Path:
    # Always load save.json from the same directory as this script
    script_dir = Path(__file__).resolve().parent
    save_path = script_dir / "save.json"

    with save_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    folder = Path(data["path"]).expanduser()
    return folder

def pick_latest_pdf(folder: Path, allowed_prefixes=("entgeltnachweis_", "entgeltabrechnung_")) -> Optional[Path]:
    """
    Picks the PDF with the highest YYYYMM in the filename.
    Only considers PDFs that start with one of allowed_prefixes (case-insensitive).
    """
    folder = Path(folder)
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Folder not found or not a directory: {folder}")

    best_dt = None
    best_path = None

    for p in folder.iterdir():
        if not p.is_file() or p.suffix.lower() != ".pdf":
            continue

        n = p.name.lower()
        if allowed_prefixes and not any(n.startswith(pref) for pref in allowed_prefixes):
            continue

        dt = extract_yyyymm_from_name(p.name)
        if not dt:
            continue

        if best_dt is None or dt > best_dt:
            best_dt = dt
            best_path = p

    return best_path


def main():
    folder = get_folder_from_save()
    latest_pdf = pick_latest_pdf(folder)

    print("PDF folder:", folder)

    if not latest_pdf:
        print("No matching payslip PDFs found (prefix Entgeltnachweis_/Entgeltabrechnung_ + YYYYMM).")
        return

    print("Latest payslip PDF:", latest_pdf.name)

    text = extract_pdf_text(latest_pdf)
    if not text.strip():
        print("PDF text extraction returned empty. This PDF might be scanned (would require OCR).")
        return

    payout = find_payout_amount(text)
    if not payout:
        print("No payout found using current keywords.")
        # helpful debugging: show lines that contain Überweisung/Zahlungen
        hits = [ln for ln in text.splitlines() if "Überweisung" in ln or "Zahlungen" in ln or "ueberweisung" in ln.lower()]
        if hits:
            print("\nLines containing Überweisung/Zahlungen:")
            for h in hits[:20]:
                print("  ", h)
        return

    payout.file = latest_pdf.name

    print("\n--- PAYOUT FOUND ---")
    print("File:", payout.file)
    print("Raw amount:", payout.raw_amount)
    print("Parsed amount:", f"{payout.amount:.2f} €")
    print("Matched line:", payout.matched_line)


if __name__ == "__main__":
    main()
