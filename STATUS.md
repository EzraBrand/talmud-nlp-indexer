# Project Status & Next Steps (as of 2025-05-03)

## Summary

This project aims to analyze and tag the Babylonian Talmud using NLP. It fetches text from the Sefaria API, processes both English and Hebrew versions, generates tags, and saves results.

## Work Completed

1.  **Core Modules**:
    *   `api.py`: Fetches text from Sefaria API.
    *   `processor.py`: Processes English text (spaCy for NER, noun chunks) and Hebrew text (AlephBERT via transformers for embeddings).
    *   `tagging.py`: Generates tags based on entities (PERSON, GPE) and keyword matching in noun phrases. Includes basic topic modeling (`extract_topics`) using scikit-learn LDA.
    *   `main.py`: Orchestrates fetching, processing, and saving results for a specified range (currently Berakhot 2a-7a). Saves output to `data/` directory as JSON.
2.  **Dependency Management**: `requirements.txt` is up-to-date. Resolved an issue with `torch` version compatibility.
3.  **Testing Framework**:
    *   Added `pytest` and `pytest-mock` to dependencies.
    *   Created `tests/` directory.
    *   Implemented unit tests with mocks for:
        *   `api.py` (`tests/test_api.py`): Tested URL construction and method calls. Verified live API fetching manually via `test_fetch.py` (now removed).
        *   `processor.py` (`tests/test_processor.py`): Tested English and Hebrew processing logic, mocking `spacy` and `transformers` models. Resolved `torch._C` import error by reinstalling `torch` and `transformers`.
        *   `tagging.py` (`tests/test_tagging.py`): Tested tag generation from entities and noun phrases, including deduplication. Tested `extract_topics` by mocking `scikit-learn`'s `CountVectorizer` and `LatentDirichletAllocation`.
    *   All 9 tests are currently passing.
4.  **Documentation**: Updated `README.md` with current features, setup, running, and testing instructions.

## Current Status

*   The basic pipeline (fetch -> process -> tag -> save) is functional for the specified range in `main.py`.
*   Core components (`api`, `processor`, `tagging`) have unit tests with reasonable coverage of their current logic.
*   The tagging logic is basic, relying on simple entity mapping and keyword checks. Topic modeling results from `extract_topics` are not currently integrated into `generate_tags`.
*   Error handling in `main.py` is present but could be more robust.
*   Serialization in `main.py` handles basic data but explicitly excludes complex objects like spaCy docs or full embeddings (only embedding shape is saved).
*   `main.py` correctly uses the individual `SefariaAPI`, `TextProcessor`, and `TalmudTagger` components.

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
