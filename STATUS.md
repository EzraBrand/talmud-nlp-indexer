# Project Status & Next Steps (as of 2025-05-03)

## Summary

This project aims to analyze and tag the Babylonian Talmud using NLP. It fetches text from the Sefaria API, processes both English and Hebrew versions, generates tags, and saves results.

## Work Completed

1.  **Core Modules**:
    *   `api.py`: Fetches text from Sefaria API.
    *   `processor.py`: 
        *   Processes Hebrew text (AlephBERT via transformers for embeddings), removing HTML tags.
        *   Processes English text by **first extracting only bolded text** (using regex `<b>.*?</b>`) and then using spaCy for NER and noun chunks. This focuses analysis on the direct translation, excluding commentary.
    *   `tagging.py`: Generates tags based on entities (PERSON, GPE) and keyword matching in noun phrases from the processed (bolded) English text. Includes basic topic modeling (`extract_topics`) using scikit-learn LDA (not yet integrated into tags).
    *   `main.py`: Orchestrates fetching, processing (using the updated `processor.py` logic), and saving results for a specified range (currently Berakhot 2a-7a). Saves output to `data/` directory as JSON.
2.  **Dependency Management**: `requirements.txt` is up-to-date. Resolved an issue with `torch` version compatibility.
3.  **Testing Framework**:
    *   Added `pytest` and `pytest-mock` to dependencies.
    *   Created `tests/` directory.
    *   Implemented unit tests with mocks for:
        *   `api.py` (`tests/test_api.py`)
        *   `processor.py` (`tests/test_processor.py`) - Updated to test the bold-text extraction logic.
        *   `tagging.py` (`tests/test_tagging.py`)
    *   Implemented integration test for `main.py` (`tests/test_main.py`) using mocks.
    *   All 11 tests are currently passing.
4.  **Documentation**: Updated `README.md` with current features (including bold text processing), setup, running, and testing instructions.
5.  **Execution**: Successfully ran `main.py` to fetch, process (using bold-only English text), and save data for Berakhot 2a-7a using the live Sefaria API. Verified that HTML remnants are removed and tags reflect the focus on bolded text.

## Current Status

*   The pipeline (fetch -> process bolded EN / clean HE -> tag -> save) is functional and tested (unit & integration) for the specified range.
*   English analysis is now specifically targeted at the bolded translation text.
*   The tagging logic is basic, relying on simple entity mapping and keyword checks from the bolded English text. Topic modeling results from `extract_topics` are not currently integrated into `generate_tags`.
*   Error handling in `main.py` is present but could be more robust.
*   Serialization in `main.py` handles basic data but explicitly excludes complex objects like spaCy docs or full embeddings (only embedding shape is saved).

## Suggested Next Steps

1.  **Refine Tagging Logic (`tagging.py`)**:
    *   Integrate the results from `extract_topics` into `generate_tags` (e.g., add `topic:<top_word>` tags based on the bolded English text).
    *   Expand keyword rules for `topic:`, `halacha:`, and `aggadah:` tags based on domain knowledge, considering the context of the bolded text.
    *   Consider using Hebrew analysis (e.g., embeddings, potential future NER) for tagging in addition to the English analysis.
2.  **Enhance Hebrew Processing (`processor.py`)**: Explore more advanced Hebrew NLP tasks beyond embeddings if needed (e.g., morphological analysis, NER if a suitable model exists).
3.  **Configuration**: Move settings like the target tractate/pages from `main.py` into a configuration file or command-line arguments.
4.  **Error Handling & Logging**: Implement more robust error handling and add proper logging throughout the application.
5.  **Data Storage**: Consider alternative storage solutions if JSON files become unwieldy (e.g., a database, document store). Decide how to store/use the large Hebrew embeddings if needed beyond just their shape.
