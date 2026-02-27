import csv
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PDF_PATH = Path(r"c:\Users\ezrab\Downloads\Index_of_Online_Entries_on_Personalities.pdf")
OUT_CSV = REPO / "data" / "glossary_initial" / "personality_index_seed.csv"

QID_RE = re.compile(r"(Q\d{3,})")
HEBREW_RE = re.compile(r"[\u0590-\u05FF]")


def extract_text_from_pdf(pdf_path: Path) -> str:
    cmd = ["pdftotext", "-layout", str(pdf_path), "-"]
    result = subprocess.run(cmd, check=True, capture_output=True)
    return result.stdout.decode("utf-8", errors="replace")


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_english_chunk(line_after_qid: str) -> str:
    # Keep only leading Latin-ish segment before Hebrew begins.
    out = []
    for ch in line_after_qid:
        if HEBREW_RE.search(ch):
            break
        out.append(ch)
    prefix = "".join(out)
    prefix = prefix.replace("\u202a", " ").replace("\u202c", " ")
    prefix = normalize_spaces(prefix)
    if not prefix:
        return ""

    # Pull the strongest title-like phrase.
    m = re.search(r"([A-Za-z0-9][A-Za-z0-9'.,()\-\/ ]{1,120})", prefix)
    if not m:
        return ""
    phrase = normalize_spaces(m.group(1))
    phrase = phrase.strip(".,;:- ")
    if len(phrase) < 2:
        return ""
    return phrase


def parse_hebrew_chunk(line_after_qid: str) -> str:
    m = re.search(r"([\u0590-\u05FF][\u0590-\u05FF\s\"'()\-\u05BE]{1,120})", line_after_qid)
    if not m:
        return ""
    return normalize_spaces(m.group(1)).strip(".,;:- ")


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Missing PDF: {PDF_PATH}")

    text = extract_text_from_pdf(PDF_PATH)
    rows = []
    seen = set()
    page_no = 1

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Page number markers from pdftotext form-feed output.
        if line.isdigit() and len(line) <= 3:
            page_no = int(line)
            continue

        qid_match = QID_RE.search(line)
        if not qid_match:
            continue
        qid = qid_match.group(1)
        rest = line[qid_match.end():].strip()
        en_name = parse_english_chunk(rest)
        he_name = parse_hebrew_chunk(rest)

        key = (qid, en_name.lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "wikidata_id": qid,
                "wikipedia_en_name_from_pdf": en_name,
                "wikipedia_he_name_from_pdf": he_name,
                "pdf_page": str(page_no),
            }
        )

    rows.sort(key=lambda r: (r["wikidata_id"], r["wikipedia_en_name_from_pdf"].lower()))
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "wikidata_id",
                "wikipedia_en_name_from_pdf",
                "wikipedia_he_name_from_pdf",
                "pdf_page",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    non_empty_en = sum(1 for r in rows if r["wikipedia_en_name_from_pdf"])
    non_empty_he = sum(1 for r in rows if r["wikipedia_he_name_from_pdf"])
    print(f"rows={len(rows)}")
    print(f"with_en_name={non_empty_en}")
    print(f"with_he_name={non_empty_he}")
    print(f"out={OUT_CSV}")


if __name__ == "__main__":
    main()
