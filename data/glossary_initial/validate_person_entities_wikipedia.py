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
SEED_PATH = REPO / "data" / "glossary_initial" / "personality_index_seed.csv"
REVIEW_DIR = REPO / "data" / "glossary_initial"

EN_API = "https://en.wikipedia.org/w/api.php"
WD_API = "https://www.wikidata.org/w/api.php"
UA = "codex-person-entity-validator/1.0"


def norm_key(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("ḥ", "h").replace("Ḥ", "h")
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def wiki_title_from_en_url(url: str) -> str:
    if not url:
        return ""
    marker = "/wiki/"
    i = url.find(marker)
    if i < 0:
        return ""
    title = url[i + len(marker):].split("#", 1)[0]
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


def query_en_title(title: str) -> Tuple[str, str, str]:
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
        return "", "", ""
    page = next(iter(pages.values()))
    if "missing" in page:
        return "", "", ""
    canonical_title = (page.get("title") or "").strip()
    qid = (page.get("pageprops", {}) or {}).get("wikibase_item", "").strip()
    ll = page.get("langlinks") or []
    he_title = (ll[0].get("*") or "").strip() if ll else ""
    return canonical_title, qid, he_title


def query_wikidata_qid(qid: str) -> Tuple[str, str, str]:
    data = fetch_json(
        WD_API,
        {
            "action": "wbgetentities",
            "format": "json",
            "ids": qid,
            "props": "sitelinks|labels",
        },
    )
    entity = data.get("entities", {}).get(qid, {})
    if not entity or entity.get("missing") == "":
        return "", "", ""
    sitelinks = entity.get("sitelinks", {}) or {}
    labels = entity.get("labels", {}) or {}
    en_title = (sitelinks.get("enwiki", {}) or {}).get("title", "").strip()
    he_title = (sitelinks.get("hewiki", {}) or {}).get("title", "").strip()
    he_label = (labels.get("he", {}) or {}).get("value", "").strip()
    return en_title, he_title, he_label


def load_seed_map(seed_path: Path) -> Dict[str, str]:
    if not seed_path.exists():
        return {}
    out = {}
    with seed_path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            qid = (r.get("wikidata_id") or "").strip()
            en_name = (r.get("wikipedia_en_name_from_pdf") or "").strip()
            if not qid:
                continue
            if en_name:
                out[norm_key(en_name)] = qid
    return out


def is_name_row(r: Dict[str, str]) -> bool:
    cats = (r.get("categories") or "").split(";")
    return any(c.strip() == "names" for c in cats)


def iter_aliases(r: Dict[str, str]) -> List[str]:
    vals = [(r.get("term") or "").strip()]
    vals.extend(v.strip() for v in (r.get("variant_names") or "").split(";") if v.strip())
    seen = set()
    out = []
    for v in vals:
        k = v.lower()
        if not v or k in seen:
            continue
        seen.add(k)
        out.append(v)
    return out


def validate_and_enrich_row(r: Dict[str, str], seed_map: Dict[str, str]) -> Dict[str, str]:
    result = {
        "status": "",
        "qid": "",
        "en_title": "",
        "he_title": "",
        "source": "",
        "note": "",
    }
    current_en = (r.get("wikipedia_en") or "").strip()

    if current_en:
        title = wiki_title_from_en_url(current_en)
        if not title:
            result["status"] = "invalid_en_url"
            result["note"] = "Could not parse title from wikipedia_en URL."
            return result
        en_title, qid, he_title = query_en_title(title)
        if not en_title:
            result["status"] = "en_missing"
            result["note"] = f"EN title missing: {title}"
            return result
        result.update(
            {
                "status": "validated_existing_en",
                "qid": qid,
                "en_title": en_title,
                "he_title": he_title,
                "source": "enwiki_existing",
            }
        )
        return result

    aliases = iter_aliases(r)
    for alias in aliases:
        qid = seed_map.get(norm_key(alias), "")
        if qid:
            en_title, he_title, he_label = query_wikidata_qid(qid)
            if en_title:
                result.update(
                    {
                        "status": "matched_from_pdf_seed_qid",
                        "qid": qid,
                        "en_title": en_title,
                        "he_title": he_title or he_label,
                        "source": "wikidata_seed_qid",
                    }
                )
                return result
            if he_title or he_label:
                result.update(
                    {
                        "status": "matched_from_pdf_seed_qid_he_only",
                        "qid": qid,
                        "en_title": "",
                        "he_title": he_title or he_label,
                        "source": "wikidata_seed_qid",
                    }
                )
                return result

    for alias in aliases[:3]:
        en_title, qid, he_title = query_en_title(alias)
        if en_title and norm_key(en_title) == norm_key(alias):
            result.update(
                {
                    "status": "matched_exact_title",
                    "qid": qid,
                    "en_title": en_title,
                    "he_title": he_title,
                    "source": "enwiki_exact_title",
                }
            )
            return result

    result["status"] = "unresolved"
    result["note"] = "No confident match from seed QID or exact EN title."
    return result


def run(args: argparse.Namespace) -> None:
    if args.only_missing_en and args.only_existing_en:
        raise ValueError("Use only one of --only-missing-en or --only-existing-en.")

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    seed_map = load_seed_map(SEED_PATH)

    name_rows = [r for r in rows if is_name_row(r)]
    target = [r for r in name_rows if args.only_missing_en is False or not (r.get("wikipedia_en") or "").strip()]
    if args.only_existing_en:
        target = [r for r in target if (r.get("wikipedia_en") or "").strip()]
    if args.seed_exact_only:
        exact = []
        for r in target:
            aliases = iter_aliases(r)
            if any(norm_key(a) in seed_map for a in aliases):
                exact.append(r)
        target = exact
    target = target[args.offset : args.offset + args.limit]

    review_rows = []
    updated = 0
    for idx, r in enumerate(target, start=1):
        res = validate_and_enrich_row(r, seed_map)
        review_rows.append(
            {
                "term": r.get("term", ""),
                "variant_names": r.get("variant_names", ""),
                "old_wikipedia_en": r.get("wikipedia_en", ""),
                "old_wikipedia_he": r.get("wikipedia_he", ""),
                "old_hebrew_term": r.get("hebrew_term", ""),
                "status": res["status"],
                "source": res["source"],
                "qid": res["qid"],
                "new_en_title": res["en_title"],
                "new_he_title": res["he_title"],
                "note": res["note"],
            }
        )

        changed = False
        if res["en_title"]:
            new_en = en_url_from_title(res["en_title"])
            if (r.get("wikipedia_en") or "") != new_en:
                r["wikipedia_en"] = new_en
                changed = True
        if res["he_title"]:
            new_he = he_url_from_title(res["he_title"])
            if (r.get("wikipedia_he") or "") != new_he:
                r["wikipedia_he"] = new_he
                changed = True
            if not (r.get("hebrew_term") or "").strip():
                r["hebrew_term"] = res["he_title"]
                changed = True
        if res["en_title"] or res["he_title"]:
            if not (r.get("wiki_match_source") or "").strip():
                r["wiki_match_source"] = res["source"]
                changed = True
        if changed:
            updated += 1

        if idx % 25 == 0:
            print(f"processed={idx}/{len(target)} updated={updated}")
        time.sleep(args.sleep_seconds)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    review_path = REVIEW_DIR / f"person_entity_validation_review_{stamp}.csv"
    with review_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "term",
                "variant_names",
                "old_wikipedia_en",
                "old_wikipedia_he",
                "old_hebrew_term",
                "status",
                "source",
                "qid",
                "new_en_title",
                "new_he_title",
                "note",
            ],
        )
        w.writeheader()
        w.writerows(review_rows)

    if args.write:
        fieldnames = list(rows[0].keys()) if rows else []
        with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    status_counts = {}
    for rr in review_rows:
        status_counts[rr["status"]] = status_counts.get(rr["status"], 0) + 1

    print(f"review={review_path}")
    print(f"processed={len(target)} updated={updated} write={args.write}")
    for k in sorted(status_counts.keys()):
        print(f"status_{k}={status_counts[k]}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate/enrich person entities via Wikipedia/Wikidata in small batches.")
    p.add_argument("--offset", type=int, default=0, help="Start offset among filtered name rows.")
    p.add_argument("--limit", type=int, default=100, help="Rows to process in this run.")
    p.add_argument("--sleep-seconds", type=float, default=0.15, help="Delay between requests.")
    p.add_argument("--only-missing-en", action="store_true", help="Only process rows missing wikipedia_en.")
    p.add_argument("--only-existing-en", action="store_true", help="Only process rows already having wikipedia_en.")
    p.add_argument("--seed-exact-only", action="store_true", help="Only process rows where term/alias exactly matches a seeded PDF EN name.")
    p.add_argument("--write", action="store_true", help="Write updates back to CSV files.")
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
