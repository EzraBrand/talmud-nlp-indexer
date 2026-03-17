from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


WORD_RE = re.compile(r"[A-Za-z]+")
TARGETS = ("rabbi", "rav", "shmuel")
CONCORDANCE_BEFORE = 10
CONCORDANCE_AFTER = 20
MAX_CONCORDANCE = 10


@dataclass(frozen=True)
class Token:
    text: str
    lower: str


def tokenize(text: str) -> list[Token]:
    return [Token(match.group(0), match.group(0).lower()) for match in WORD_RE.finditer(text)]


def load_name_sequences(path: Path) -> list[tuple[str, tuple[str, ...]]]:
    entries: list[tuple[str, tuple[str, ...]]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        tokens = tuple(token.lower() for token in WORD_RE.findall(line))
        if tokens:
            entries.append((line, tokens))
    return entries


def build_name_index(
    names: list[tuple[str, tuple[str, ...]]],
) -> tuple[dict[str, dict[int, set[tuple[str, ...]]]], list[int]]:
    by_first: dict[str, dict[int, set[tuple[str, ...]]]] = defaultdict(lambda: defaultdict(set))
    lengths: set[int] = set()
    for _, tokens in names:
        by_first[tokens[0]][len(tokens)].add(tokens)
        lengths.add(len(tokens))
    return by_first, sorted(lengths, reverse=True)


def mark_non_target_names(
    corpus_tokens: list[Token],
    by_first: dict[str, dict[int, set[tuple[str, ...]]]],
    lengths_desc: list[int],
) -> list[bool]:
    occupied = [False] * len(corpus_tokens)
    lower_tokens = [token.lower for token in corpus_tokens]
    total = len(corpus_tokens)

    for index in range(total):
        if occupied[index]:
            continue
        candidates_by_length = by_first.get(lower_tokens[index])
        if not candidates_by_length:
            continue
        for length in lengths_desc:
            if length == 1:
                continue
            candidates = candidates_by_length.get(length)
            if not candidates:
                continue
            end = index + length
            if end > total or any(occupied[index:end]):
                continue
            if tuple(lower_tokens[index:end]) in candidates:
                for span_index in range(index, end):
                    occupied[span_index] = True
                break
    return occupied


def concordance_line(tokens: list[Token], match_index: int) -> str:
    start = max(0, match_index - CONCORDANCE_BEFORE)
    end = min(len(tokens), match_index + 1 + CONCORDANCE_AFTER)
    words: list[str] = []
    for idx in range(start, end):
        word = tokens[idx].text
        if idx == match_index:
            word = f"<<{word}>>"
        words.append(word)
    return " ".join(words)


def count_targets(corpus_tokens: list[Token], occupied: list[bool]) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for target in TARGETS:
        indices = [
            idx
            for idx, token in enumerate(corpus_tokens)
            if not occupied[idx] and token.lower == target
        ]
        results[target] = {
            "count": len(indices),
            "concordance": [concordance_line(corpus_tokens, idx) for idx in indices[:MAX_CONCORDANCE]],
        }
    return results


def render_report(
    corpus_path: Path,
    gazetteer_path: Path,
    corpus_tokens: list[Token],
    non_target_names: list[tuple[str, tuple[str, ...]]],
    occupied: list[bool],
    results: dict[str, dict[str, object]],
) -> str:
    removed_token_count = sum(1 for flag in occupied if flag)
    lines: list[str] = [
        "Mononymic Rabbinic Figure Counts in the Talmud",
        "==============================================",
        "",
        f"Corpus: {corpus_path}",
        f"Gazetteer: {gazetteer_path}",
        "",
        "Method:",
        "- Tokenize the English Talmud corpus into alphabetic word tokens.",
        "- Tokenize all gazetteer entries the same way.",
        "- Keep all gazetteer names except the exact one-word targets: Rabbi, Rav, Shmuel.",
        "- Match other gazetteer names greedily from longest token-length to shortest at each token position.",
        "- Mark matched spans as removed so shorter names cannot double count inside longer names.",
        "- Count the remaining standalone target tokens and print up to 10 concordance lines for review.",
        "",
        f"Corpus token count: {len(corpus_tokens)}",
        f"Non-target gazetteer entries used for removal: {len(non_target_names)}",
        f"Tokens removed as part of non-target name spans: {removed_token_count}",
        "",
        "Counts:",
    ]

    for target in TARGETS:
        lines.append(f"- {target.title()}: {results[target]['count']}")

    for target in TARGETS:
        lines.extend(
            [
                "",
                f"{target.title()} concordance (up to {MAX_CONCORDANCE} results)",
                "-" * (len(target) + 34),
            ]
        )
        concordance = results[target]["concordance"]
        if not concordance:
            lines.append("(no residual matches)")
            continue
        for idx, line in enumerate(concordance, start=1):
            lines.append(f"{idx}. {line}")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--corpus", type=Path, default=root / "data" / "talmud_full_english.txt")
    parser.add_argument("--gazetteer", type=Path, default=root / "data" / "talmud_names_gazetteer.txt")
    parser.add_argument("--output", type=Path, default=root / "mononyms" / "mononym_counts.txt")
    args = parser.parse_args()

    corpus_tokens = tokenize(args.corpus.read_text(encoding="utf-8", errors="replace"))
    all_names = load_name_sequences(args.gazetteer)
    non_target_names = [
        entry
        for entry in all_names
        if not (len(entry[1]) == 1 and entry[1][0] in TARGETS)
    ]
    by_first, lengths_desc = build_name_index(non_target_names)
    occupied = mark_non_target_names(corpus_tokens, by_first, lengths_desc)
    results = count_targets(corpus_tokens, occupied)
    report = render_report(
        corpus_path=args.corpus,
        gazetteer_path=args.gazetteer,
        corpus_tokens=corpus_tokens,
        non_target_names=non_target_names,
        occupied=occupied,
        results=results,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(args.output)
    for target in TARGETS:
        print(f"{target}\t{results[target]['count']}")


if __name__ == "__main__":
    main()
