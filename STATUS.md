# Project Status & Next Steps (as of 2025-05-03)

## Summary

This project aims to analyze and tag the Babylonian Talmud using NLP. It fetches text from the Sefaria API, processes both English and Hebrew versions, generates tags, and saves results.

## Work Completed

1.  **Core Modules**:
    *   `api.py`: Fetches text from Sefaria API.
    *   `processor.py`: Processes English text (spaCy for NER, noun chunks) and Hebrew text (AlephBERT via transformers for embeddings). Includes text cleaning logic (extracting bold for English, removing HTML for Hebrew).
    *   `tagging.py`: Generates tags based on entities (PERSON, GPE/LOC), keyword matching in noun phrases, and comprehensive matching against gazetteers (Talmudic names, toponyms, concepts; Biblical names, places, nations). Includes basic topic modeling (`extract_topics`) using scikit-learn LDA (currently not integrated into tag generation).
    *   `main.py`: Orchestrates fetching, processing, and saving results for a specified range (currently Berakhot 2a-7a). Saves output to `data/` directory as JSON. Correctly imports and utilizes `SefariaAPI`, `TextProcessor`, and `TalmudTagger`.
2.  **Dependency Management**: `requirements.txt` is up-to-date.
3.  **Testing Framework**:
    *   Added `pytest` and `pytest-mock`.
    *   Implemented unit tests with mocks for `api.py`, `processor.py`, and `tagging.py` in the `tests/` directory.
    *   All existing tests are passing.
4.  **Documentation**: Updated `README.md` with current features, setup, running, and testing instructions.
5.  **Gazetteers**: Added gazetteers for biblical names, places, and nations.

## Current Status

*   The basic pipeline (fetch -> process -> tag -> save) is functional for the specified range in `main.py`.
*   Core components (`api`, `processor`, `tagging`) have unit tests with reasonable coverage of their current logic.
*   The tagging logic uses NER, keyword checks, and gazetteer matching. Biblical tags are prioritized over general Talmudic tags where applicable. Topic modeling results from `extract_topics` are not currently integrated into `generate_tags`.
*   Error handling in `main.py` is present but could be more robust.
*   Serialization in `main.py` handles basic data, excluding complex objects like spaCy docs or full embeddings (only embedding shape is saved).

## Suggested Next Steps

1.  **Integration Testing (`main.py`)**: Create tests for `main.py` to ensure the components work together correctly. This will likely involve mocking the `SefariaAPI`, `TextProcessor`, `TalmudTagger`, file system operations (`open`, `os.makedirs`), and `json.dump`.
2.  **Refine Tagging Logic (`tagging.py`)**:
    *   Integrate the results from `extract_topics` into `generate_tags` (e.g., add `topic:<top_word>` tags).
    *   Expand keyword rules for `topic:`, `halacha:`, and `aggadah:` tags based on domain knowledge.
    *   Consider using Hebrew entities/analysis for tagging if possible (requires a Hebrew NER model or different approach).
3.  **Enhance Hebrew Processing (`processor.py`)**: Explore more advanced Hebrew NLP tasks beyond embeddings if needed (e.g., morphological analysis, NER if a suitable model exists).
4.  **Configuration**: Move settings like the target tractate/pages from `main.py` into a configuration file or command-line arguments.
5.  **Error Handling & Logging**: Implement more robust error handling and add proper logging throughout the application.
6.  **Data Storage**: Consider alternative storage solutions if JSON files become unwieldy (e.g., a database, document store). Decide how to store/use the large Hebrew embeddings if needed beyond just their shape.
7.  **Expand Test Coverage**: Add more tests, particularly for edge cases and the interactions refined in `tagging.py` (e.g., tag prioritization).
