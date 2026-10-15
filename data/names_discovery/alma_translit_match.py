#!/usr/bin/env python3
"""Match Alma place names (academic transliteration) to the gazetteers and the Steinsaltz
English corpus with a loose transliteration key. Run after build_alma.py.

Outputs: alma/alma_places_matched.csv  alma_places.csv plus key-based matches
"""
import csv, re, sys, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent
# Repo layout: this folder is data/names_discovery/ and the gazetteers are in data/.
ALMA = ROOT / "alma"
DATA = ROOT / "data" if (ROOT / "data").is_dir() else ROOT.parent


def key(s):
    """Loose key for transliterated names: Tsippori = Tzippori, Yavneh = Yavne,
    Bethther = Beitar is NOT covered (different vowels), Erets = Eretz."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"<[^>]+>|\[[^\]]*\]", " ", s)
    s = re.sub(r"^the\s+", "", s.strip())
    s = re.sub(r"[’‘'`ʼ\-\s]", "", s)
    for a, b in (("ts", "tz"), ("q", "k"), ("kh", "k"), ("ch", "k"), ("ph", "f"), ("th", "t"),
                 ("w", "v"), ("ei", "e"), ("ai", "a"), ("ee", "i"), ("y", "i"), ("j", "i")):
        s = s.replace(a, b)
    s = re.sub(r"h$", "", s)              # Yavneh = Yavne
    s = re.sub(r"(.)\1", r"\1", s)        # Tsippori = Tzipori
    s = re.sub(r"(?<=[^aeiou])h", "", s)  # drop h after a consonant (dh, gh ...)
    return s


def lines(p):
    return [l.strip() for l in p.read_text(encoding="utf-8-sig").splitlines() if l.strip()]


def main():
    places = list(csv.DictReader(open(ALMA / "alma_places.csv", encoding="utf-8-sig")))
    known = defaultdict(set)
    for src, f in (("talmud_toponyms", "talmud_toponyms_gazetteer.txt"), ("bible_places", "bible_places_gazetteer.txt"),
                   ("nations", "nations_and_demonyms_gazetteer.txt")):
        for n in lines(DATA / f):
            known[key(n)].add(f"{src}:{n}")
    # Capitalized 1-3 word sequences in the corpus, keyed the same way.
    text = re.sub(r"<[^>]+>", " ", (DATA / "talmud_full_english.txt").read_text(encoding="utf-8-sig"))
    text = unicodedata.normalize("NFC", text)
    cap = r"[A-ZḤṬẒṢŠ][\w’']*"
    seqs = Counter()
    for m in re.finditer(rf"(?<![\w’']){cap}(?:[\s\-]+(?:(?:ha|Ha|de|De)-?)?{cap})?(?:\s+{cap})?", text):
        ws = re.split(r"\s+", m.group(0))
        for k in range(1, len(ws) + 1):
            seqs[" ".join(ws[:k])] += 1
    corpus = defaultdict(Counter)
    for s, c in seqs.items():
        corpus[key(s)][s] += c
    out = []
    for p in places:
        k = key(p["alma_place_english"])
        p["translit_key"] = k
        p["gazetteer_key_match"] = "; ".join(sorted(known.get(k, [])))
        forms = corpus.get(k, Counter())
        p["corpus_key_forms"] = "; ".join(f"{s} {c}" for s, c in forms.most_common(4))
        p["corpus_key_count"] = sum(forms.values())
        out.append(p)
    with open(ALMA / "alma_places_matched.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    exact = sum(1 for p in out if p["gazetteer_match"])
    keyed = sum(1 for p in out if p["gazetteer_key_match"])
    new_in_corpus = [p for p in out if not p["gazetteer_match"] and not p["gazetteer_key_match"] and p["corpus_key_count"]]
    print("places", len(out), "| gazetteer exact", exact, "| gazetteer by key", keyed,
          "| not on lists but found in corpus by key", len(new_in_corpus))
    for p in sorted(new_in_corpus, key=lambda p: -p["corpus_key_count"]):
        print(p["corpus_key_count"], "|", p["alma_place_english"], "->", p["corpus_key_forms"], "| BT", p["alma_mentions_babylonian_talmud"])
    # Review file: proposed toponym additions, with flags for likely non-place readings.
    names = {l.lower() for f in ("talmud_names_gazetteer.txt", "bible_names_gazetteer.txt") for l in lines(DATA / f)}
    english = {w.lower() for w in re.findall(r"(?<![\w’'])[a-z]+(?![\w’'])", text)}
    rows = []
    for p in sorted(new_in_corpus, key=lambda p: -p["corpus_key_count"]):
        form = Counter(dict(f.rsplit(" ", 1) for f in p["corpus_key_forms"].split("; ")))
        top = max(form, key=lambda s: int(form[s]))
        flags = []
        if top.lower() in names: flags.append("also a person name in names gazetteer")
        if top.lower() in english: flags.append("also a lowercase English word in corpus")
        rows.append({"alma_place_english": p["alma_place_english"], "alma_place_hebrew": p["alma_place_hebrew"],
                     "alma_place_type": p["alma_place_type"], "proposed_corpus_form": top,
                     "corpus_key_forms": p["corpus_key_forms"], "corpus_key_count": p["corpus_key_count"],
                     "alma_mentions_babylonian_talmud": p["alma_mentions_babylonian_talmud"],
                     "alma_longitude": p["alma_longitude"], "alma_latitude": p["alma_latitude"],
                     "review_flags": "; ".join(flags)})
    with open(ALMA / "alma_toponym_additions_review.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("\nkey-only gazetteer matches:")
    for p in out:
        if p["gazetteer_key_match"] and not p["gazetteer_match"]:
            print(p["alma_place_english"], "->", p["gazetteer_key_match"])


if __name__ == "__main__":
    main()
