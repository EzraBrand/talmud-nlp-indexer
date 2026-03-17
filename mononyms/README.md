# Mononym Counts

This folder contains a reproducible count for major mononymic rabbinic figures in the English Talmud corpus:

- `Rabbi` for Yehuda HaNasi
- `Rav` for Abba Arikha
- `Shmuel` for Shmuel bar Abba
- `Rava`
- `Abaye`
- `Rabba`

## Method

The script tokenizes the corpus and the rabbinic name gazetteer, removes all other gazetteer names first, and does that matching from longest token span to shortest so shorter names do not double count inside longer names.

After that removal pass, it counts the residual one-word target tokens and writes a concordance with up to 10 examples for each target.

## Files

- `count_mononyms.py`: counting script
- `mononym_counts.txt`: generated report with counts and concordance

## Usage

```bash
python mononyms/count_mononyms.py
```
