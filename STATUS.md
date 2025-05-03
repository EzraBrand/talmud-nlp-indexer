# Project Status & Next Steps (as of 2025-05-03)

## Summary

This project aims to analyze and tag the Babylonian Talmud using NLP. It fetches text from the Sefaria API, processes both English and Hebrew versions, generates tags, and saves results in both JSON and Markdown formats.

## Work Completed

1.  **Core Modules**:
    *   `api.py`: Fetches text from Sefaria API.
    *   `processor.py`: Processes English text (spaCy for NER, noun chunks, **identifying italicized words**) and Hebrew text (AlephBERT via transformers for embeddings). Includes text cleaning logic (extracting bold for English, removing HTML for Hebrew).
    *   `tagging.py`: Generates tags based on entities (PERSON, GPE/LOC), keyword matching in noun phrases, comprehensive matching against gazetteers (Talmudic names, toponyms, concepts; Biblical names, places, nations), and integration of topic modeling results (top word per topic). Logic updated to check name gazetteers before assigning place tags to GPE/LOC entities.
    *   `main.py`: Orchestrates fetching, processing, and saving results for a specified range (currently Berakhot 2a-7a). Saves output to `data/` directory as JSON **and Markdown**. **Markdown generation includes prioritized gazetteer tags and excludes specific spaCy labels (ORG, WORK_OF_ART, etc.).** Correctly imports and utilizes `SefariaAPI`, `TextProcessor`, and `TalmudTagger`.
2.  **Dependency Management**: `requirements.txt` is up-to-date.
3.  **Testing Framework**:
    *   Added `pytest` and `pytest-mock`.
    *   Implemented unit tests with mocks for `api.py`, `processor.py`, and `tagging.py` in the `tests/` directory.
    *   Added integration tests for `main.py` (`tests/test_main.py`).
    *   Added specific test case for topic tag generation in `tests/test_tagging.py`.
    *   **Added test case for Markdown generation, including tag prioritization and spaCy label exclusion.**
    *   All existing tests are passing.
4.  **Documentation**: Updated `README.md` with current features, setup, running, and testing instructions.
5.  **Gazetteers**:
    *   Added gazetteers for biblical names, places, and nations.
    *   Expanded `talmud_concepts_gazetteer.txt` with key terms (Mercy, Anger, Prayer, Divine Presence).
    *   Significantly expanded `bible_names_gazetteer.txt`.
6.  **Output Formats**:
    *   JSON output for structured data.
    *   **Markdown output for human-readable summaries, including tags, italicized words, and annotated text.**
7.  **Tag Refinement**:
    *   **Excluded less relevant spaCy entity labels (ORG, WORK_OF_ART, FAC, PRODUCT, EVENT, LAW, LANGUAGE, PERCENT, MONEY) from Markdown output.**

## Current Status

*   The basic pipeline (fetch -> process -> tag -> save JSON/Markdown) is functional for the specified range in `main.py`.
*   Core components (`api`, `processor`, `tagging`) have unit tests with reasonable coverage of their current logic, including the integration of topic tags, refined place tagging logic, and Markdown generation.
*   The tagging logic uses NER, keyword checks, gazetteer matching (including expanded biblical lists), and topic modeling results. Biblical tags are prioritized over general Talmudic tags where applicable.
*   Markdown output provides a human-readable view of the analysis, incorporating tag prioritization and exclusion rules.
*   Error handling in `main.py` is present but could be more robust.
*   Serialization in `main.py` handles basic data, excluding complex objects like spaCy docs or full embeddings (only embedding shape is saved).

## Suggested Next Steps

0a. **Add initial processing of text**: Input and incorporate my mapping table / dictionary ('Lord' to 'YHWH'; 'gentile' to 'non-Jew'; etc)

0b. **Add original Hebrew to the markdown files**.

0c. **Entity Linking to Wikipedia / wiki ID**.

0d. **Refine the tagging, especially default spacy tagging:** exclude 'cardinal' tag from 'one'. full names should be tagged as a single name. E.g. 'Rabbi X ben Y' .

0e. **Expand input range:** Test on a longer range of Talmud berakhot; expand to the first 20 pages.

1. **Refine Tagging Logic (`tagging.py`) & Gazetteers**:
    *   Expand keyword rules for `topic:`, `halacha:`, and `aggadah:` tags based on domain knowledge.
    *   Consider using Hebrew entities/analysis for tagging if possible (requires a Hebrew NER model or different approach).
    *   Refine how topic modeling results are used (e.g., use more than just the top word, filter irrelevant topic words).
2.  **Enhance Hebrew Processing (`processor.py`)**: Explore more advanced Hebrew NLP tasks beyond embeddings if needed (e.g., morphological analysis, NER if a suitable model exists).
3.  **Configuration**: Move settings like the target tractate/pages from `main.py` into a configuration file or command-line arguments.
4.  **Error Handling & Logging**: Implement more robust error handling and add proper logging throughout the application.
5.  **Data Storage**: Consider alternative storage solutions if JSON files become unwieldy (e.g., a database, document store). Decide how to store/use the large Hebrew embeddings if needed beyond just their shape.
6.  **Expand Test Coverage**: Add more tests, particularly for edge cases and the interactions refined in `tagging.py` (e.g., tag prioritization, topic tag relevance, place tag exceptions).
