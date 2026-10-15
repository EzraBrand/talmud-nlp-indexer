#!/usr/bin/env python3
"""Merge the Alma ArcGIS export and compare its places with the toponym gazetteer.

Usage: py -3.13 -I build_alma.py   (paths are fixed relative to this file)

Inputs : alma/alma_records_*.geojson (main records layer, paged), alma/alma_archaeology.geojson
         data/talmud_toponyms_gazetteer.txt, data/bible_places_gazetteer.txt,
         data/nations_and_demonyms_gazetteer.txt, data/talmud_full_english.txt
Outputs: alma/alma_records.csv            one row per place mention (all columns + lon/lat)
         alma/alma_archaeology.csv        archaeology layer
         alma/alma_places.csv             one row per Alma place, with gazetteer and corpus checks
         alma/alma_toponyms_in_corpus.txt Alma names that occur in the corpus and are on no list
"""
import csv, json, re, sys, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent
# Repo layout: this folder is data/names_discovery/ and the gazetteers are in data/.
ALMA = ROOT / "alma"
DATA = ROOT / "data" if (ROOT / "data").is_dir() else ROOT.parent


def load_features(paths):
    rows = []
    for p in paths:
        for f in json.loads(p.read_text(encoding="utf-8"))["features"]:
            r = dict(f["properties"])
            lon, lat = (f.get("geometry") or {}).get("coordinates", [None, None])[:2]
            r["geom_lon"], r["geom_lat"] = lon, lat
            rows.append(r)
    return rows


def write_csv(path, rows, header=None):
    header = header or list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def fold(s):
    """Loose key: no diacritics, apostrophes, hyphens, case or leading 'the'."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[’‘'`ʼ\-]", "", s)
    s = re.sub(r"<[^>]+>|\[[^\]]*\]", " ", s)
    s = re.sub(r"^the\s+", "", s.strip())
    return re.sub(r"\s+", " ", s).strip()


def gazetteer(path):
    return [l.strip() for l in path.read_text(encoding="utf-8-sig").splitlines() if l.strip()]


def main():
    pages = sorted(ALMA.glob("alma_records_*.geojson"), key=lambda p: int(p.stem.rsplit("_", 1)[1]))
    recs = load_features(pages)
    ids = Counter(r["OBJECTID"] for r in recs)
    assert all(c == 1 for c in ids.values()), "duplicate OBJECTIDs across pages"
    recs.sort(key=lambda r: r["OBJECTID"])
    write_csv(ALMA / "alma_records.csv", recs)
    arch = load_features([ALMA / "alma_archaeology.geojson"])
    write_csv(ALMA / "alma_archaeology.csv", arch)
    print("records", len(recs), "archaeology", len(arch))

    topo = gazetteer(DATA / "talmud_toponyms_gazetteer.txt")
    bible = gazetteer(DATA / "bible_places_gazetteer.txt")
    nations = gazetteer(DATA / "nations_and_demonyms_gazetteer.txt")
    known = {}
    for src, names in (("talmud_toponyms", topo), ("bible_places", bible), ("nations", nations)):
        for n in names:
            known.setdefault(fold(n), []).append(src)

    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", (DATA / "talmud_full_english.txt").read_text(encoding="utf-8-sig")))
    text = unicodedata.normalize("NFC", text)
    by_place = defaultdict(list)
    for r in recs:
        by_place[(r["Place_English"] or "").strip()].append(r)

    # Word n-gram counts, built only for n-grams that start like an Alma name.
    tok = re.compile(r"\w+(?:[’']\w+)*")
    words = tok.findall(text)
    fwords = [fold(w) for w in words]
    def ngram_counts(seq, names):
        heads = {n.split()[0] for n in names if n}
        maxlen = max(len(n.split()) for n in names if n)
        c = Counter()
        for i, w in enumerate(seq):
            if w in heads:
                for k in range(1, maxlen + 1):
                    c[" ".join(seq[i:i + k])] += 1
        return c
    exact_c = ngram_counts(words, [" ".join(tok.findall(n)) for n in by_place])
    loose_c = ngram_counts(fwords, [" ".join(fold(w) for w in tok.findall(n)) for n in by_place])

    def corpus_count(name):
        # Exact (case-sensitive) and loose (folded) counts of whole words.
        ws = tok.findall(name)
        return exact_c[" ".join(ws)], loose_c[" ".join(fold(w) for w in ws)]
    places = []
    for name, rs in sorted(by_place.items(), key=lambda kv: -len(kv[1])):
        if not name:
            continue
        sources = Counter(r["Source_English"] for r in rs)
        bt = sum(c for s, c in sources.items() if s and "babylonian talmud" in s.lower())
        forms = Counter(r["Place_name_appears_as"] for r in rs if r["Place_name_appears_as"])
        exact, loose = corpus_count(name)
        k = fold(name)
        places.append({
            "alma_place_english": name,
            "alma_place_hebrew": rs[0]["Place_Hebrew"],
            "alma_place_type": rs[0]["place_type"],
            "alma_mentions": len(rs),
            "alma_mentions_babylonian_talmud": bt,
            "alma_periods": "; ".join(f"{p} {c}" for p, c in Counter(r["Period"] for r in rs).most_common()),
            "alma_top_sources": "; ".join(f"{s} {c}" for s, c in sources.most_common(5)),
            "alma_hebrew_forms_in_text": "; ".join(f for f, _ in forms.most_common(8)),
            "alma_longitude": rs[0]["Longtitude"] or rs[0]["geom_lon"],
            "alma_latitude": rs[0]["Latitude"] or rs[0]["geom_lat"],
            "gazetteer_match": "; ".join(known.get(k, [])),
            "corpus_exact_count": exact,
            "corpus_loose_count": loose,
        })
    write_csv(ALMA / "alma_places.csv", places)

    in_list = [p for p in places if p["gazetteer_match"]]
    missing = [p for p in places if not p["gazetteer_match"]]
    in_corpus = [p for p in missing if p["corpus_exact_count"] > 0]
    (ALMA / "alma_toponyms_in_corpus.txt").write_text(
        "\n".join(sorted(p["alma_place_english"] for p in in_corpus)) + "\n", encoding="utf-8")
    print("unique Alma places", len(places))
    print("already on a list", len(in_list))
    print("not on any list", len(missing), "| of these in the corpus (exact)", len(in_corpus),
          "| loose only", sum(1 for p in missing if not p["corpus_exact_count"] and p["corpus_loose_count"]))
    print("source names:", Counter(r["Source_English"] for r in recs).most_common(25))
    print("\nNot on a list, in corpus, by corpus count:")
    for p in sorted(in_corpus, key=lambda p: -p["corpus_exact_count"])[:60]:
        print(p["corpus_exact_count"], "|", p["alma_place_english"], "|", p["alma_place_type"], "| BT", p["alma_mentions_babylonian_talmud"])


if __name__ == "__main__":
    main()
