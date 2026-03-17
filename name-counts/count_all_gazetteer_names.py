from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)


@dataclass(frozen=True)
class Token:
    lower: str


@dataclass(frozen=True)
class GazetteerEntry:
    line_number: int
    term: str
    tokens: tuple[str, ...]


def tokenize_corpus(text: str) -> list[Token]:
    return [Token(match.group(0).lower()) for match in WORD_RE.finditer(text)]


def load_gazetteer(path: Path) -> list[GazetteerEntry]:
    entries: list[GazetteerEntry] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        term = raw_line.strip()
        if not term:
            continue
        tokens = tuple(token.lower() for token in WORD_RE.findall(term))
        if not tokens:
            continue
        entries.append(GazetteerEntry(line_number=line_number, term=term, tokens=tokens))
    return entries


def build_name_index(
    entries: list[GazetteerEntry],
) -> tuple[dict[str, dict[int, set[tuple[str, ...]]]], list[int]]:
    by_first: dict[str, dict[int, set[tuple[str, ...]]]] = defaultdict(lambda: defaultdict(set))
    lengths: set[int] = set()
    for entry in entries:
        by_first[entry.tokens[0]][len(entry.tokens)].add(entry.tokens)
        lengths.add(len(entry.tokens))
    return by_first, sorted(lengths, reverse=True)


def greedy_count_sequences(
    corpus_tokens: list[Token],
    by_first: dict[str, dict[int, set[tuple[str, ...]]]],
    lengths_desc: list[int],
) -> Counter[tuple[str, ...]]:
    counts: Counter[tuple[str, ...]] = Counter()
    occupied = [False] * len(corpus_tokens)
    lowered = [token.lower for token in corpus_tokens]
    total = len(corpus_tokens)

    for index in range(total):
        if occupied[index]:
            continue
        candidates_by_length = by_first.get(lowered[index])
        if not candidates_by_length:
            continue
        for length in lengths_desc:
            candidates = candidates_by_length.get(length)
            if not candidates:
                continue
            end = index + length
            if end > total or any(occupied[index:end]):
                continue
            window = tuple(lowered[index:end])
            if window in candidates:
                counts[window] += 1
                for span_index in range(index, end):
                    occupied[span_index] = True
                break
    return counts


def write_review_csv(
    output_path: Path,
    entries: list[GazetteerEntry],
    counts: Counter[tuple[str, ...]],
) -> None:
    token_frequency = Counter(entry.tokens for entry in entries)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "gazetteer_line_number",
                "term",
                "normalized_term",
                "token_length",
                "greedy_match_count",
                "duplicate_token_sequence_entries",
            ],
        )
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "gazetteer_line_number": entry.line_number,
                    "term": entry.term,
                    "normalized_term": " ".join(entry.tokens),
                    "token_length": len(entry.tokens),
                    "greedy_match_count": counts.get(entry.tokens, 0),
                    "duplicate_token_sequence_entries": token_frequency[entry.tokens],
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--corpus", type=Path, default=root / "data" / "talmud_full_english.txt")
    parser.add_argument("--gazetteer", type=Path, default=root / "data" / "talmud_names_gazetteer.txt")
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "name-counts" / "gazetteer_name_counts_review.csv",
    )
    args = parser.parse_args()

    corpus_tokens = tokenize_corpus(args.corpus.read_text(encoding="utf-8", errors="replace"))
    entries = load_gazetteer(args.gazetteer)
    by_first, lengths_desc = build_name_index(entries)
    counts = greedy_count_sequences(corpus_tokens, by_first, lengths_desc)
    write_review_csv(args.output, entries, counts)

    print(args.output)
    print(f"entries\t{len(entries)}")
    print(f"matched_unique_sequences\t{len(counts)}")


if __name__ == "__main__":
    main()
