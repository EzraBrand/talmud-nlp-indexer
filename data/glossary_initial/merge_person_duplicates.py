import argparse
import csv
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple

REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / "docs" / "glossary" / "glossary_initial_v4.csv"
REVIEW_DIR = REPO / "data" / "glossary_initial"

NON_PERSON_HINTS = (
    "dynasty",
    "kingdom",
    "empire",
    "list of",
    "disambiguation",
    "chaldea",
    "personifications of death",
)


def split_semicolon(s: str) -> List[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(";") if x.strip()]


def unique_preserve(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def wiki_title_from_url(url: str) -> str:
    if not url:
        return ""
    marker = "/wiki/"
    i = url.find(marker)
    if i < 0:
        return ""
    title = url[i + len(marker):].split("#", 1)[0]
    return urllib.parse.unquote(title).replace("_", " ").strip()


def to_int(s: str) -> int:
    try:
        return int((s or "").strip())
    except Exception:
        return 0


def choose_canonical_idx(rows: List[Dict[str, str]], wiki_title: str) -> int:
    wiki_l = wiki_title.lower().strip()

    def score(row: Dict[str, str]) -> Tuple[int, int, int, str]:
        term = (row.get("term") or "").strip()
        t = term.lower()
        val = 0

        # Strongly prefer exact title match from Wikipedia.
        if wiki_l and t == wiki_l:
            val += 200

        # Prefer explicit rabbinic title for person pages when present.
        if t.startswith("rabbi "):
            val += 60
        elif t.startswith("rav "):
            val += 50
        elif t.startswith("rabban "):
            val += 45

        # Prefer generic form over age epithet variant.
        if " the elder" in t or " the younger" in t:
            val -= 40

        # Prefer shorter name when otherwise similar.
        val -= len(term)

        # Prefer higher corpus count when tie.
        count = to_int(row.get("talmud_corpus_count", "0"))
        return (val, count, -len(term), t)

    best_idx = 0
    best_score = score(rows[0])
    for i in range(1, len(rows)):
        s = score(rows[i])
        if s > best_score:
            best_score = s
            best_idx = i
    return best_idx


def is_names_row(row: Dict[str, str]) -> bool:
    return "names" in split_semicolon(row.get("categories", ""))


def is_person_page_hint(wiki_title: str) -> bool:
    t = wiki_title.lower()
    return not any(h in t for h in NON_PERSON_HINTS)


def merge_cluster(rows: List[Dict[str, str]]) -> Dict[str, str]:
    wiki_title = wiki_title_from_url(rows[0].get("wikipedia_en", ""))
    keep_idx = choose_canonical_idx(rows, wiki_title)
    keep = dict(rows[keep_idx])

    all_terms = []
    all_categories = []
    all_variants = []
    count_sum = 0
    source_parts = []

    for r in rows:
        term = (r.get("term") or "").strip()
        if term:
            all_terms.append(term)
        all_categories.extend(split_semicolon(r.get("categories", "")))
        all_variants.extend(split_semicolon(r.get("variant_names", "")))
        count_sum += to_int(r.get("talmud_corpus_count", "0"))
        src = (r.get("wiki_match_source") or "").strip()
        if src:
            source_parts.extend(split_semicolon(src))

    canonical = (keep.get("term") or "").strip()
    merged_variants = unique_preserve([*all_variants, *all_terms])
    merged_variants = [v for v in merged_variants if v.lower() != canonical.lower()]

    keep["categories"] = "; ".join(sorted(unique_preserve(all_categories), key=lambda x: x.lower()))
    keep["variant_names"] = "; ".join(sorted(unique_preserve(merged_variants), key=lambda x: x.lower()))
    keep["talmud_corpus_count"] = str(count_sum)

    merged_sources = unique_preserve(source_parts + ["merge_same_enwiki"])
    keep["wiki_match_source"] = "; ".join(merged_sources)
    keep["chavrutai_search_url"] = "https://chavrutai.com/search?q=" + urllib.parse.quote(canonical, safe="")

    if not (keep.get("selected_anchor_text") or "").strip():
        keep["selected_anchor_text"] = canonical
    return keep


def run(args: argparse.Namespace) -> None:
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError("No rows found.")

    groups = {}
    for idx, r in enumerate(rows):
        if not is_names_row(r):
            continue
        en = (r.get("wikipedia_en") or "").strip()
        if not en:
            continue
        groups.setdefault(en, []).append((idx, r))

    review = []
    remove_indices = set()
    replacement_rows = {}

    for en_url, pairs in groups.items():
        if len(pairs) < 2:
            continue
        wiki_title = wiki_title_from_url(en_url)
        terms = [p[1].get("term", "") for p in pairs]

        if not is_person_page_hint(wiki_title):
            review.append(
                {
                    "action": "skip_non_person_hint",
                    "wikipedia_en": en_url,
                    "wikipedia_title": wiki_title,
                    "terms": " | ".join(terms),
                    "canonical_term": "",
                }
            )
            continue

        merged = merge_cluster([p[1] for p in pairs])
        keep_term = merged.get("term", "")
        keep_row_idx = pairs[0][0]
        keep_original_idx = None
        for i, (_, row) in enumerate(pairs):
            if row.get("term", "").strip().lower() == keep_term.strip().lower():
                keep_original_idx = i
                break
        if keep_original_idx is None:
            keep_original_idx = 0
        keep_row_idx = pairs[keep_original_idx][0]

        replacement_rows[keep_row_idx] = merged
        for i, (orig_idx, _) in enumerate(pairs):
            if i != keep_original_idx:
                remove_indices.add(orig_idx)

        review.append(
            {
                "action": "merge",
                "wikipedia_en": en_url,
                "wikipedia_title": wiki_title,
                "terms": " | ".join(terms),
                "canonical_term": keep_term,
            }
        )

    new_rows = []
    for idx, r in enumerate(rows):
        if idx in remove_indices:
            continue
        if idx in replacement_rows:
            new_rows.append(replacement_rows[idx])
        else:
            new_rows.append(r)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    review_path = REVIEW_DIR / f"person_merge_review_{stamp}.csv"
    with review_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["action", "wikipedia_en", "wikipedia_title", "terms", "canonical_term"],
        )
        w.writeheader()
        w.writerows(review)

    merged_count = sum(1 for r in review if r["action"] == "merge")
    skipped_count = sum(1 for r in review if r["action"] == "skip_non_person_hint")

    if args.write:
        fields = list(new_rows[0].keys())
        with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(new_rows)

    print(f"review={review_path}")
    print(f"clusters_total={len(review)} merged={merged_count} skipped={skipped_count}")
    print(f"rows_before={len(rows)} rows_after={len(new_rows)} removed={len(rows)-len(new_rows)} write={args.write}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Merge duplicate person rows sharing the same EN Wikipedia URL.")
    p.add_argument("--write", action="store_true", help="Write merged CSV files.")
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
