# Talmud NLP Indexer

An NLP-powered system for programmatically analyzing, indexing, and tagging the Talmud Bavli page by page.

## Project Overview

This project uses modern natural language processing techniques to analyze and tag the content of the Talmud Bavli (Babylonian Talmud). 

It leverages both the original Hebrew/Aramaic text and English translations available through the Sefaria API.

See also my overview at my blog: 
["Mapping the Talmud: Scalable Natural Language Processing (NLP) for Named Entities, Topics, and Tags in the Talmudic Corpus"](https://www.ezrabrand.com/p/mapping-the-talmud-scalable-natural) (May 04, 2025)

### Initial Focus
- Tractate Berakhot (first 10 pages: 2a-7a)
- Developing core NLP pipelines for Talmudic text (`processor.py`)
- Fetching data from Sefaria API (`api.py`)
- Creating a basic tagging system (`tagging.py`)
- Orchestrating the process (`main.py`)

## Features

- Automated fetching of Talmudic text via Sefaria API
- Bilingual processing (Hebrew using AlephBERT via `transformers`, English using `spacy`)
- Text analysis including named entity recognition, noun phrase extraction (English), and embeddings (Hebrew)
- Basic topic modeling (using `scikit-learn`) and keyword/entity-based tag generation, including matching against expanded Talmudic and Biblical gazetteers (names, places, concepts) and integration of topic modeling results. Logic improved to check name gazetteers before assigning place tags to reduce misclassification.
- Storage of processed results as JSON files (`data/` directory)
- Generation of human-readable Markdown summaries (`data/` directory) including tags, italicized words, and annotated text with prioritized gazetteer tags and exclusion of less relevant spaCy labels (e.g., ORG, WORK_OF_ART).

## Setup

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Running

Execute the main script to process the default range (Berakhot 2a-7a):

```bash
python main.py
```

Results will be saved as JSON and Markdown files in the `data/` directory.

## Testing

This project uses `pytest` for unit testing.

1.  Ensure development dependencies are installed (included in `requirements.txt`):
    ```bash
    pip install -r requirements.txt 
    ```
2.  Run the tests from the root directory:
    ```bash
    python -m pytest
    ```

Tests for API interaction, text processing, and tagging logic are located in the `tests/` directory. Mocks are used to isolate components and avoid external dependencies (like network calls or loading large models) during testing.
