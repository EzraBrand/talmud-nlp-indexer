#!/usr/bin/env python3
"""Find the Steinsaltz (William Davidson) English form of each Alma place in the Bavli.

For each Alma record from the Babylonian Talmud, open the Sefaria segments of that amud
(sefaria/<Tractate>_he.json and _en.json, aligned segment by segment), find the segment
whose Aramaic contains Alma's Hebrew form of the place, and collect capitalized English
phrases from the parallel English segment. Per place, the phrase that occurs in most of
its aligned segments and is rare across the whole Bavli is proposed as its English form.
Transliteration similarity to the Alma name is a tie-break only.

Run after build_alma.py and alma_translit_match.py:  py -3.13 -I alma_bavli_align.py
Outputs: alma/alma_bavli_alignment.csv          one row per Alma place
         alma/alma_bavli_mentions_aligned.csv   one row per Alma Bavli record
"""
import csv, json, math, re, sys, unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent
# Repo layout: this folder is data/names_discovery/ and the gazetteers are in data/.
ALMA, SEF = ROOT / "alma", ROOT / "sefaria"
DATA = ROOT / "data" if (ROOT / "data").is_dir() else ROOT.parent
sys.path.insert(0, str(ROOT))
from alma_translit_match import key  # noqa: E402

NIKUD = re.compile(r"[֑-ׇ]")
PREFIX = "ובדשלמכהו"
# Phrase starts that are never place names by themselves.
SKIP = set("""A An And As At But By For From He How I If In It Its Mishna Gemara Rabbi Rav Rabban
Rabbis Sages Sage Master Merciful Torah Shabbat The There These They This Those To We What When
Where Which Who Why With You One Two Three Is Are Was Were Not No Yes So Since Therefore Rather
However Also Even Just Only Then Now Here Holy Blessed Be God Lord Heaven Festival Shema Amen
MISHNA GEMARA Come Say Didn’t Isn’t Doesn’t Granted Apparently Actually Abaye Rava Rabba Shmuel
Even Perhaps Rather According""".split())
CAPW = r"[A-ZḤṬẒṢŠ][\w’'\-]*"
LINKW = r"(?:of|ha|de|the|HaGadol)"


def heb_tokens(s):
    s = NIKUD.sub("", re.sub(r"<[^>]+>", " ", s or ""))
    s = s.replace("״", "").replace('"', "")
    return re.findall(r"[א-ת׳']+", s)


def skel(tok):
    """Consonant skeleton: no vav/yod after the first letter, final aleph = he, no geresh."""
    tok = tok.replace("׳", "").replace("'", "")
    tok = tok[:1] + re.sub(r"[וי]", "", tok[1:])
    return re.sub(r"א$", "ה", tok)


def strip_prefix(tok, stem):
    """True if tok is stem with up to two prefix letters (בציפורי, ובציפורי)."""
    return tok == stem or (tok.endswith(stem) and len(tok) - len(stem) <= 2 and all(c in PREFIX for c in tok[: len(tok) - len(stem)]))


def contains_form(toks, form_toks, stems):
    n = len(form_toks)
    if n and any(toks[i:i + n] == form_toks for i in range(len(toks) - n + 1)):
        return True
    # Fallback: the form or the place's Hebrew name, with prefixes, compared as skeletons
    # (spelling with or without vav/yod, final aleph or he).
    sk = [skel(t) for t in toks]
    for st in list(stems) + ([tuple(form_toks)] if form_toks else []):
        st = [skel(t) for t in st]
        m = len(st)
        for i in range(len(sk) - m + 1):
            if (strip_prefix(sk[i], st[0]) or strip_prefix(sk[i], skel(st[0][1:]) if len(st[0]) > 3 and st[0][0] in PREFIX else st[0])) \
                    and sk[i + 1:i + m] == st[1:]:
                return True
    return False


def en_phrases(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    out = set()
    for m in re.finditer(rf"(?<![\w’']){CAPW}(?:\s+(?:{LINKW}\s+)?{CAPW}){{0,3}}", s):
        ws = m.group(0).split()
        for i in range(len(ws)):
            if ws[i] in SKIP or ws[i] in ("of", "ha", "de", "the"):
                continue
            for j in range(i + 1, min(len(ws), i + 4) + 1):
                if ws[j - 1] in ("of", "ha", "de", "the"):
                    continue
                out.add(" ".join(ws[i:j]).rstrip("’'"))
    # 'the X River', 'the Sea of X' style without capital start handled by the above.
    return out


HEB2LAT = {"ב": "b", "ג": "g", "ד": "d", "ז": "z", "ח": "h", "ט": "t", "כ": "k", "ך": "k", "ל": "l",
           "מ": "m", "ם": "m", "נ": "n", "ן": "n", "ס": "s", "פ": "p", "ף": "p", "צ": "z", "ץ": "z",
           "ק": "k", "ר": "r", "ש": "s", "ת": "t"}


def heb_skel(heb):
    """Latin consonant skeleton of a Hebrew name (vowel letters dropped): אשור -> sr."""
    s = "".join(HEB2LAT.get(c, "") for c in NIKUD.sub("", heb))
    return re.sub(r"(.)\1", r"\1", s)


def lat_skel(name):
    """Consonant skeleton of an English rendering, on the same scale: Asshur -> sr."""
    s = unicodedata.normalize("NFKD", name.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    for a, b in (("tz", "z"), ("ts", "z"), ("sh", "s"), ("kh", "k"), ("ch", "k"), ("ph", "p"), ("th", "t"),
                 ("c", "k"), ("q", "k"), ("f", "p"), ("v", "b"), ("w", "b"), ("x", "ks")):
        s = s.replace(a, b)
    s = re.sub(r"[^bcdgklmnprstz]", "", s)
    return re.sub(r"(.)\1", r"\1", s)


def tkey(s):
    """Tractate key: Ketubbot = Ketubot, Menahot = Menachot, Megila = Megillah, Chulin = Chullin."""
    s = re.sub(r"[^a-z]", "", s.lower()).replace("ch", "h").replace("kh", "h")
    s = re.sub(r"(.)\1", r"\1", s)
    return re.sub(r"h$", "", s)


def main():
    files = sorted(SEF.glob("*_en.json"))
    seg_en, seg_he = {}, {}
    for fe in files:
        tr = fe.name[:-8].replace("_", " ")
        fh = SEF / (fe.name[:-8] + "_he.json")
        if not fh.exists():
            continue
        en = json.loads(fe.read_text(encoding="utf-8"))["text"]
        he = json.loads(fh.read_text(encoding="utf-8"))["text"]
        for i, (ae, ah) in enumerate(zip(en, he)):
            if not ae:
                continue
            daf, amud = i // 2 + 1, "ab"[i % 2]
            seg_en[(tkey(tr), daf, amud)] = ae
            seg_he[(tkey(tr), daf, amud)] = [heb_tokens(x) for x in ah]
    print("tractates", len(files), "amudim", len(seg_en))

    df = Counter()
    for segs in seg_en.values():
        for s in segs:
            df.update(en_phrases(s))
    n_seg = sum(len(v) for v in seg_en.values())

    recs = [r for r in csv.DictReader(open(ALMA / "alma_records.csv", encoding="utf-8-sig"))
            if r["Source_English"] == "Babylonian Talmud" and r["Place_English"].strip()]
    stems_by_place = defaultdict(set)
    for r in recs:
        stem = tuple(heb_tokens(r["Place_Hebrew"]))
        if stem:
            stems_by_place[r["Place_English"].strip()].add(stem)

    mention_rows, per_place = [], defaultdict(list)
    unparsed = Counter()
    for r in recs:
        place = r["Place_English"].strip()
        m = re.match(r"BT (.+?) (\d+):([12])$", (r["Reference_English"] or "").strip())
        if not m:
            unparsed["ref"] += 1; continue
        k0 = (tkey(m.group(1)), int(m.group(2)), "a" if m.group(3) == "1" else "b")
        if k0 not in seg_en:
            unparsed[m.group(1)] += 1; continue
        form = heb_tokens(r["Place_name_appears_as"])
        # Alma references often differ from the Vilna pagination by an amud or two:
        # search the cited amud first, then the nearest ones, up to 3 amudim away.
        base = (k0[1] - 1) * 2 + (0 if k0[2] == "a" else 1)
        hits, k, offset = [], k0, ""
        for off in (0, -1, 1, -2, 2, -3, 3):
            j = base + off
            kk = (k0[0], j // 2 + 1, "ab"[j % 2])
            if kk not in seg_he:
                continue
            h = [i for i, toks in enumerate(seg_he[kk]) if contains_form(toks, form, stems_by_place[place])]
            if h:
                hits, k, offset = h, kk, off
                break
        phr = set()
        for i in hits:
            phr |= en_phrases(seg_en[k][i])
        per_place[place].append(phr)
        mention_rows.append({"alma_place_english": place, "alma_reference": r["Reference_English"],
                             "alma_form_in_text": r["Place_name_appears_as"],
                             "sefaria_ref": f"{m.group(1)} {k[1]}{k[2]}" + (f":{hits[0]+1}" if hits else ""),
                             "aligned_segments": len(hits), "amud_offset": offset,
                             "english_segment": re.sub(r"<[^>]+>", "", seg_en[k][hits[0]])[:400] if hits else ""})
    print("unparsed/unmatched refs", unparsed.most_common(8))

    places = {p["alma_place_english"]: p for p in csv.DictReader(open(ALMA / "alma_places_matched.csv", encoding="utf-8-sig"))}
    known = defaultdict(set)
    for f in ("talmud_toponyms_gazetteer.txt", "bible_places_gazetteer.txt", "nations_and_demonyms_gazetteer.txt",
              "talmud_names_gazetteer.txt", "bible_names_gazetteer.txt"):
        for l in (DATA / f).read_text(encoding="utf-8-sig").splitlines():
            if l.strip():
                known[l.strip().lower()].add(f.replace("_gazetteer.txt", ""))

    out = []
    for place, sets in sorted(per_place.items(), key=lambda kv: -len(kv[1])):
        aligned = [s for s in sets if s]
        hskel = heb_skel(next(iter(stems_by_place[place]), ("",))[0] if stems_by_place[place] else "")
        hskels = {heb_skel(" ".join(st)) for st in stems_by_place[place]}
        cover = Counter()
        for s in aligned:
            cover.update(s)
        scored = []
        for ph, c in cover.items():
            share = c / len(aligned)
            idf = math.log(n_seg / df[ph])
            sim = SequenceMatcher(None, key(place), key(ph)).ratio()
            # Sound match of the Hebrew name: drop prefix words such as Mount / Kefar / Beit.
            words = ph.split()
            tails = {" ".join(words[i:]) for i in range(len(words))}
            hsim = max((SequenceMatcher(None, hs, lat_skel(t)).ratio() for hs in hskels for t in tails if hs), default=0)
            few = len(aligned) <= 2
            score = share * idf + (1.5 if few else 1.0) * sim + (3.0 if few else 1.5) * hsim + 0.2 * len(words) * share
            scored.append((score, share, idf, max(sim, hsim), ph))
        scored.sort(reverse=True)
        best = []
        for s in scored:
            if any((s[4] in b[4] or b[4] in s[4]) for b in best):
                continue
            best.append(s)
            if len(best) == 3:
                break
        p = places.get(place, {})
        row = {"alma_place_english": place, "alma_place_hebrew": p.get("alma_place_hebrew", ""),
               "alma_place_type": p.get("alma_place_type", ""), "alma_bavli_records": len(sets),
               "aligned_records": len(aligned),
               "existing_gazetteer_match": p.get("gazetteer_match") or p.get("gazetteer_key_match", "")}
        for i in range(3):
            b = best[i] if i < len(best) else None
            row[f"english_form_{i+1}"] = b[4] if b else ""
            row[f"share_{i+1}"] = round(b[1], 2) if b else ""
            row[f"bavli_segments_with_form_{i+1}"] = df[b[4]] if b else ""
            row[f"translit_similarity_{i+1}"] = round(b[3], 2) if b else ""
            row[f"form_on_lists_{i+1}"] = "; ".join(sorted(known.get(b[4].lower(), []))) if b else ""
        s1 = row["share_1"] or 0
        row["confidence"] = ("high" if len(aligned) >= 2 and s1 >= 0.6 or (len(aligned) == 1 and (row["translit_similarity_1"] or 0) >= 0.7)
                             else "medium" if s1 >= 0.4 else "low")
        lists1 = row["form_on_lists_1"]
        row["status"] = ("no_alignment" if not row["english_form_1"] else
                         "already_toponym" if any(x in lists1 for x in ("toponyms", "bible_places", "nations")) else
                         "on_names_list_only" if lists1 else "new_toponym_candidate")
        out.append(row)
    for path, rows in ((ALMA / "alma_bavli_alignment.csv", out), (ALMA / "alma_bavli_mentions_aligned.csv", mention_rows)):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("Bavli records", len(mention_rows), "aligned", sum(1 for r in mention_rows if r["aligned_segments"]))
    print("places", len(out), Counter(r["status"] for r in out), Counter(r["confidence"] for r in out))
    for r in out:
        print(r["confidence"][0], r["status"][:10], r["aligned_records"], "|", r["alma_place_english"], "->",
              r["english_form_1"], r["share_1"], "|", r["form_on_lists_1"], "| alt:", r["english_form_2"], "/", r["english_form_3"])


if __name__ == "__main__":
    main()
