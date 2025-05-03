"""
Main script for running the Talmud NLP Indexer.
"""
import json
import os
from api import SefariaAPI
from processor import TextProcessor
from tagging import TalmudTagger
import numpy as np  # Add numpy for potential use with embeddings if needed later


def main():
    """Run the Talmud NLP Indexer."""
    # Initialize components
    sefaria_api = SefariaAPI()
    text_processor = TextProcessor()
    tagger = TalmudTagger()

    # Define the target pages (first 10 pages of Berakhot)
    tractate = "Berakhot"
    start_daf = "2a"  # Talmud usually starts at page 2
    end_daf = "7a"    # This covers 10 pages (2a, 2b, 3a, 3b, ..., 7a)

    # Create directory for output
    os.makedirs("data", exist_ok=True)

    # Process each page
    for num in range(2, 8):  # Pages 2-7
        for side in ['a', 'b']:
            # Skip 7b as it's the 11th page
            if num == 7 and side == 'b':
                continue

            daf = f"{num}{side}"
            print(f"Processing {tractate}.{daf}...")

            try:
                # 1. Fetch data
                page_data = sefaria_api.fetch_talmud_page(tractate, daf)

                # Extract texts (handle potential missing keys and list format)
                en_text = ' '.join(page_data.get('text', [])) if isinstance(page_data.get('text'), list) else page_data.get('text', '')
                he_text = ' '.join(page_data.get('he', [])) if isinstance(page_data.get('he'), list) else page_data.get('he', '')

                # Clean texts
                en_text_cleaned = text_processor.clean_text(en_text, 'en')
                he_text_cleaned = text_processor.clean_text(he_text, 'he')

                # 2. Process texts
                en_processed = text_processor.process_english(en_text_cleaned)
                he_processed = text_processor.process_hebrew(he_text_cleaned)

                # 3. Generate tags (currently uses only English processed data)
                # Placeholder for topics - could be generated per page or per tractate
                topics = []  # tagger.extract_topics([en_text_cleaned]) # Example: topics per page
                tags = tagger.generate_tags(en_processed, topics)

                # 4. Assemble result (similar structure to before)
                result = {
                    'ref': page_data.get('ref', f"{tractate}.{daf}"),
                    'en_text': en_text,
                    'he_text': he_text,
                    'en_processed': en_processed,  # Contains doc, entities, etc.
                    'he_processed': he_processed,  # Contains embeddings, tokens
                    'tags': tags
                }

                # Save results
                output_file = f"data/{tractate}_{daf}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    # Convert complex objects for JSON serialization
                    serializable_result = {}
                    serializable_result['ref'] = result['ref']
                    serializable_result['en_text'] = result['en_text']
                    serializable_result['he_text'] = result['he_text']
                    # Extract serializable parts from en_processed
                    serializable_result['en_processed'] = {
                        k: v for k, v in result['en_processed'].items()
                        if k in ['entities', 'noun_phrases', 'sentences']
                    }
                    # Extract serializable parts from he_processed (e.g., embedding shape)
                    embedding_tensor = result['he_processed'].get('embeddings')
                    if embedding_tensor is not None:
                        # Detach tensor from computation graph and convert to numpy array, then list
                        # embedding_list = embedding_tensor.detach().cpu().numpy().tolist()
                        # serializable_result['he_processed'] = {'embeddings': embedding_list}
                        # Or just save the shape as before
                        serializable_result['he_processed'] = {'embedding_shape': list(embedding_tensor.shape)}
                    else:
                        serializable_result['he_processed'] = {'embedding_shape': None}

                    serializable_result['tags'] = result['tags']

                    json.dump(serializable_result, f, ensure_ascii=False, indent=2)

                print(f"Saved results to {output_file}")

                # Print tags
                print(f"Tags: {', '.join(result['tags'])}\n" + "-" * 50)

            except Exception as e:
                # Print detailed error including traceback
                import traceback
                print(f"Error processing {tractate}.{daf}: {e}")
                traceback.print_exc()  # Print traceback for debugging
                print("-" * 50)

    print("Processing complete!")


def test_tagging_on_sefaria_page(tractate="Berakhot", daf="2a"):
    """Fetches a page from Sefaria, processes it, and generates tags."""
    print(f"--- Testing Tagging on {tractate} {daf} ---")
    try:
        api = SefariaAPI()
        processor = TextProcessor()
        tagger = TalmudTagger() # Uses default gazetteer paths

        # 1. Fetch data
        print(f"Fetching {tractate} {daf}...")
        page_data = api.fetch_talmud_page(tractate, daf)

        if 'en' not in page_data or not page_data['en']:
            print("Error: English text not found in fetched data.")
            return

        # 2. Clean English text (extract bold)
        raw_en_text = " ".join(page_data['en']) # Join list of strings if necessary
        print("Cleaning English text (extracting bold)...")
        cleaned_en_text = processor.clean_text(raw_en_text, 'en')
        print(f"Cleaned Text (Bold): {cleaned_en_text[:500]}...") # Print snippet

        if not cleaned_en_text:
            print("Warning: No bolded English text found to process.")
            return # Stop if no bold text found as per current logic

        # 3. Process English text
        print("Processing English text with spaCy...")
        processed_en = processor.process_english(cleaned_en_text)
        print(f"Found Entities: {processed_en.get('entities', [])}")
        print(f"Found Noun Phrases: {processed_en.get('noun_phrases', [])}")

        # 4. Generate Tags
        print("Generating tags...")
        # Currently, topics are not used in generate_tags, pass empty list
        tags = tagger.generate_tags(processed_en, topics=[])

        # 5. Print Tags
        print("--- Generated Tags ---")
        if tags:
            for tag in tags:
                print(f"- {tag}")
        else:
            print("No tags generated.")
        print("-----------------------")

    except Exception as e:
        print(f"An error occurred during testing: {e}")


if __name__ == "__main__":
    main()

    # Run the Sefaria API test