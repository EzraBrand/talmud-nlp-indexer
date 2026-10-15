# Names and toponym discovery

Regex discovery of person references and place names in the English Talmud
(`../talmud_full_english.txt`), checked against the gazetteers in `data/`, plus a link from the
Alma place-name map to the Steinsaltz English forms of its places.

All commands run from this folder (`data/names_discovery/`) with Python 3.10+ and no dependencies.

## 1. Name discovery: `discover_talmud_names.py`

```
python discover_talmud_names.py --corpus ../talmud_full_english.txt --gold ../talmud_names_gazetteer.txt --bible ../bible_names_gazetteer.txt --toponyms ../talmud_toponyms_gazetteer.txt ../bible_places_gazetteer.txt --nations ../nations_and_demonyms_gazetteer.txt --out results
```

About 40 s. `--mode broad` and `--mode baseline` give the rule sets of the earlier version
(`discover_talmud_names_v1.py`).

- **General rules, not gazetteer lists.** Titles, patronymics, speech verbs, "named X", family and
  group relations, appellations (Mar, Bar, lowercase ben), epithets (the Babylonian, HaModa’i),
  possessives (Rava’s), "the X", roles (the Sages, the tanna’im), generic people with a qualifier
  (an old man, this woman), "the generation of X", "one of the Sages".
- **Surnames come from corpus statistics:** a word that follows a titled name at least twice and is
  not itself used as a first name or a bare speaker (Nappaḥa, Shezuri, Nesia, Ḥasida, Arikha).
- **Stop lists hold English function words only**, so the rules are not tuned to the gold lists.
- **Known-place layer:** matches from the toponym, biblical-place and nations lists are labelled
  `known_toponym` / `known_nation` and are not reported as person candidates.

Results (exact span match against the two names lists, 81,266 mentions):

| Run | Precision | Recall |
|---|---|---|
| v1 broad | 64.5% | 96.5% |
| v2 recall, all spans | 62.2% | 97.4% |
| v2 recall, known places excluded | 65.3% | 97.4% |

Precision here is against the current lists only: an extraction that is not on a list can still be
a correct new name. In `results/`:

- `priority_candidates.csv`: 1,204 candidates with a structural cue or transliteration feature.
  Start here.
- `broad_only_candidates.csv`: 4,153 low-signal candidates.
- `toponym_candidates.csv`: places in "X of/from Y" phrases that are on no list.
- `rule_metrics.csv`: how many selected spans each rule supports, and how many are exact gold.
- `summary.json`, `patterns.json`, `missed_gold_mentions.csv`, `toponym_counts.csv`, `toponym_mentions.csv`.

`all_occurrences.csv` (46 MB), `cleaned_text.txt` and `bible_mentions.csv` are not committed. A run
writes them again.

## 2. Alma place-name map: Steinsaltz English forms

Source: [Alma map](https://experience.arcgis.com/experience/5ebdd921862447daa05118ad17b118a1)
(ArcGIS, owner `idowachtel_hugis`). It records 10,966 place mentions in ancient Jewish literature,
3,054 of them in the Bavli, with Alma's English and Hebrew place names, the form in the text and the
reference. No licence is stated, so the raw export is not committed. Download it with
`curl -K alma_download.curlrc`.

The Bavli link uses the William Davidson Edition from Sefaria's public export bucket. That edition
is the same English as `talmud_full_english.txt`, and its English and Aramaic are aligned segment
by segment. Download it with `curl -K sefaria_download.curlrc` (74 files, about 73 MB).

```
python build_alma.py            # merge the export; gazetteer and corpus checks per place
python alma_translit_match.py   # transliteration key (Tsippori = Tzippori, Yavneh = Yavne)
python alma_bavli_align.py      # Hebrew-guided alignment to the Steinsaltz English
```

`alma_bavli_align.py` works in three steps:
1. For each Alma Bavli record, it finds Alma's Hebrew form in the Aramaic segments of the cited
   amud. Alma's references often differ from Vilna by 1-2 amudim, so it then searches up to
   3 amudim away, nearest first.
2. It reads the parallel English segment.
3. Per place, it chooses the capitalized phrase that recurs across the place's segments, is rare
   in the Bavli, and sounds like the Hebrew name (consonant skeleton).

Result: 2,520 of 2,683 records are aligned. Of 206 places, 148 map to a form already on the
toponym lists, 39 are new toponym candidates, 5 map to the names lists only, and 14 have no
alignment.

- `alma/alma_bavli_alignment.csv`: one row per place. It gives the top 3 English forms, their
  share, Bavli frequency, similarity, the lists that have each form, confidence and status. Filter
  `status = new_toponym_candidate`. Check places with one or two mentions by hand.
- `alma/alma_bavli_mentions_aligned.csv`: one row per record, with the Sefaria reference and the
  amud offset.
- `alma/alma_toponym_additions_review.csv`: Alma places found in the corpus by spelling alone.
