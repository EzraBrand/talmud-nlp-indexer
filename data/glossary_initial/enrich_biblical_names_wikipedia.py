import argparse
import csv
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / "docs" / "glossary" / "glossary_initial_v4.csv"
REVIEW_INPUT = REPO / "data" / "glossary_initial" / "biblical_names_wikipedia_review.csv"
OUT_DIR = REPO / "data" / "glossary_initial"

EN_API = "https://en.wikipedia.org/w/api.php"
UA = "codex-biblical-name-enricher/1.0"


def norm_key(s: str) -> str:
    s = (s or "").lower().strip()
    s = s.replace("ḥ", "h").replace("Ḥ", "h")
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def split_semicolon(s: str) -> List[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(";") if x.strip()]


def is_biblical_name_row(r: Dict[str, str]) -> bool:
    return "biblicalNames" in split_semicolon(r.get("categories", ""))


def wiki_title_from_url(url: str) -> str:
    if not url:
        return ""
    marker = "/wiki/"
    i = url.find(marker)
    if i < 0:
        return ""
    title = url[i + len(marker) :].split("#", 1)[0]
    return urllib.parse.unquote(title).replace("_", " ").strip()


def en_url_from_title(title: str) -> str:
    slug = title.replace(" ", "_")
    return "https://en.wikipedia.org/wiki/" + urllib.parse.quote(slug, safe="()")


def he_url_from_title(title: str) -> str:
    slug = title.replace(" ", "_")
    return "https://he.wikipedia.org/wiki/" + urllib.parse.quote(slug, safe="()")


def fetch_json(base_url: str, params: Dict[str, str], retries: int = 5) -> Dict:
    url = base_url + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return {}


def query_en(title: str) -> Tuple[str, str, bool]:
    data = fetch_json(
        EN_API,
        {
            "action": "query",
            "format": "json",
            "redirects": "1",
            "prop": "pageprops|langlinks",
            "lllang": "he",
            "lllimit": "1",
            "titles": title,
        },
    )
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return "", "", False
    page = next(iter(pages.values()))
    if "missing" in page:
        return "", "", False
    canonical_title = (page.get("title") or "").strip()
    is_disambig = "disambiguation" in (page.get("pageprops") or {})
    links = page.get("langlinks") or []
    he_title = (links[0].get("*") or "").strip() if links else ""
    return canonical_title, he_title, is_disambig


def search_en_titles(query: str, limit: int = 5) -> List[str]:
    data = fetch_json(
        EN_API,
        {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": str(limit),
            "srprop": "",
        },
    )
    return [(x.get("title") or "").strip() for x in (data.get("query", {}).get("search", []) or []) if (x.get("title") or "").strip()]


def title_tokens(s: str) -> List[str]:
    s = s.lower()
    s = s.replace("ḥ", "h")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    toks = [t for t in s.split() if t]
    stop = {"son", "of", "ben", "bar", "the", "king", "queen", "prophet", "priest"}
    return [t for t in toks if t not in stop]


def pick_best_search_match(term: str, titles: List[str]) -> str:
    t_toks = set(title_tokens(term))
    best = ""
    best_score = -9999
    for title in titles:
        score = 0
        lt = title.lower()
        if "(biblical" in lt:
            score += 80
        if "(prophet" in lt:
            score += 60
        if "(hebrew bible" in lt:
            score += 60
        if "(judges)" in lt:
            score += 40
        cand_toks = set(title_tokens(title))
        overlap = len(t_toks.intersection(cand_toks))
        score += overlap * 20
        if norm_key(title).startswith(norm_key(term)):
            score += 30
        score -= len(title)
        if score > best_score:
            best = title
            best_score = score
    return best


def load_verified_review_map() -> Dict[str, str]:
    out = {}
    if not REVIEW_INPUT.exists():
        return out
    with REVIEW_INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            term = (r.get("term") or "").strip()
            status = (r.get("verification_status") or "").strip()
            en = (r.get("verified_wikipedia_en") or "").strip()
            if not term or not en:
                continue
            if status != "verified_exact_or_redirect":
                continue
            out[norm_key(term)] = en
    return out


def candidate_titles(term: str) -> List[str]:
    t = term.strip()
    cands = [t]
    if "," in t:
        cands.append(t.split(",", 1)[0].strip())
    # "X, son of Y" -> "X"
    cands.append(re.sub(r",?\s*son of\s+.+$", "", t, flags=re.IGNORECASE).strip())
    # "X ben Y" stays as-is; but allow first token fallback for long descriptive terms.
    if len(t.split()) > 3:
        cands.append(t.split()[0])

    out = []
    seen = set()
    for c in cands:
        if not c:
            continue
        k = c.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(c)
    return out


def run(args: argparse.Namespace) -> None:
    verified_map = load_verified_review_map()
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    targets = [r for r in rows if is_biblical_name_row(r)]
    if args.only_missing_en:
        targets = [r for r in targets if not (r.get("wikipedia_en") or "").strip()]
    if args.only_missing_he:
        targets = [r for r in targets if not (r.get("wikipedia_he") or "").strip()]
    targets = targets[args.offset : args.offset + args.limit]

    review_rows = []
    updated = 0

    for idx, r in enumerate(targets, start=1):
        term = (r.get("term") or "").strip()
        old_en = (r.get("wikipedia_en") or "").strip()
        old_he = (r.get("wikipedia_he") or "").strip()
        old_he_term = (r.get("hebrew_term") or "").strip()

        status = "unchanged"
        source = ""
        new_en = old_en
        new_he = old_he
        new_he_term = old_he_term
        note = ""

        # First path: strict verified map from prior review.
        if not old_en:
            mapped_en = verified_map.get(norm_key(term), "")
            if mapped_en:
                title = wiki_title_from_url(mapped_en)
                can_title, he_title, is_disambig = query_en(title)
                if can_title and not is_disambig:
                    new_en = en_url_from_title(can_title)
                    if he_title:
                        new_he = he_url_from_title(he_title)
                        if not new_he_term:
                            new_he_term = he_title
                    status = "matched_from_prior_verified_review"
                    source = "biblical_review_verified"
                else:
                    status = "review_map_failed_live_validation"
                    note = "Mapped EN URL failed non-disambiguation live validation."

        # Second path: API candidate titles.
        if status in ("unchanged", "review_map_failed_live_validation"):
            if not new_en:
                for cand in candidate_titles(term):
                    can_title, he_title, is_disambig = query_en(cand)
                    if not can_title or is_disambig:
                        continue
                    # Conservative: require normalized exact-ish title match for candidate itself.
                    if norm_key(can_title) != norm_key(cand):
                        continue
                    new_en = en_url_from_title(can_title)
                    if he_title:
                        new_he = he_url_from_title(he_title)
                        if not new_he_term:
                            new_he_term = he_title
                    status = "matched_exact_title_api"
                    source = "enwiki_api_exact"
                    break
                if not new_en and args.enable_search_fallback:
                    queries = [f"{term} biblical"]
                    if "," in term:
                        queries.append(f"{term.split(',', 1)[0].strip()} biblical")
                    for q in queries:
                        titles = search_en_titles(q, limit=6)
                        if not titles:
                            continue
                        chosen = pick_best_search_match(term, titles)
                        if not chosen:
                            continue
                        can_title, he_title, is_disambig = query_en(chosen)
                        if not can_title or is_disambig:
                            continue
                        new_en = en_url_from_title(can_title)
                        if he_title:
                            new_he = he_url_from_title(he_title)
                            if not new_he_term:
                                new_he_term = he_title
                        status = "matched_search_biblical_api"
                        source = "enwiki_search_biblical"
                        break
                if not new_en and status == "unchanged":
                    status = "unresolved_missing_en"

        # Third path: if EN exists but HE missing, pull langlink.
        if new_en and not new_he:
            can_title, he_title, is_disambig = query_en(wiki_title_from_url(new_en))
            if can_title and not is_disambig and he_title:
                new_he = he_url_from_title(he_title)
                if not new_he_term:
                    new_he_term = he_title
                if status == "unchanged":
                    status = "added_he_from_langlink"
                    source = "enwiki_langlink"

        changed = False
        if new_en and new_en != old_en:
            r["wikipedia_en"] = new_en
            changed = True
        if new_he and new_he != old_he:
            r["wikipedia_he"] = new_he
            changed = True
        if new_he_term and new_he_term != old_he_term:
            r["hebrew_term"] = new_he_term
            changed = True
        if changed:
            src = (r.get("wiki_match_source") or "").strip()
            src_parts = split_semicolon(src)
            if source and source not in src_parts:
                src_parts.append(source)
            if src_parts:
                r["wiki_match_source"] = "; ".join(src_parts)
            updated += 1

        review_rows.append(
            {
                "term": term,
                "old_wikipedia_en": old_en,
                "new_wikipedia_en": new_en,
                "old_wikipedia_he": old_he,
                "new_wikipedia_he": new_he,
                "old_hebrew_term": old_he_term,
                "new_hebrew_term": new_he_term,
                "status": status,
                "source": source,
                "note": note,
            }
        )

        if idx % 25 == 0:
            print(f"processed={idx}/{len(targets)} updated={updated}")
        time.sleep(args.sleep_seconds)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    review_path = OUT_DIR / f"biblical_names_enrichment_review_{stamp}.csv"
    with review_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "term",
                "old_wikipedia_en",
                "new_wikipedia_en",
                "old_wikipedia_he",
                "new_wikipedia_he",
                "old_hebrew_term",
                "new_hebrew_term",
                "status",
                "source",
                "note",
            ],
        )
        w.writeheader()
        w.writerows(review_rows)

    if args.write:
        fields = list(rows[0].keys())
        with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    status_counts = {}
    for rr in review_rows:
        status_counts[rr["status"]] = status_counts.get(rr["status"], 0) + 1

    print(f"review={review_path}")
    print(f"processed={len(targets)} updated={updated} write={args.write}")
    for k in sorted(status_counts.keys()):
        print(f"status_{k}={status_counts[k]}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Enrich biblicalNames rows with EN/HE Wikipedia links.")
    p.add_argument("--offset", type=int, default=0, help="Start offset among filtered biblical names rows.")
    p.add_argument("--limit", type=int, default=120, help="Rows to process.")
    p.add_argument("--sleep-seconds", type=float, default=0.12, help="Delay between API calls.")
    p.add_argument("--only-missing-en", action="store_true", help="Only rows missing wikipedia_en.")
    p.add_argument("--only-missing-he", action="store_true", help="Only rows missing wikipedia_he.")
    p.add_argument("--enable-search-fallback", action="store_true", help="Enable search-based fallback for ambiguous/disambiguated names.")
    p.add_argument("--write", action="store_true", help="Write changes to both CSV files.")
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
