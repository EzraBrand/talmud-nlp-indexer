"""
Main script for running the Talmud NLP Indexer.
"""
import json
import os
from api import SefariaAPI
from processor import TextProcessor
from tagging import TalmudTagger
import numpy as np  # Add numpy for potential use with embeddings if needed later
import re  # Import re for the annotation logic
import traceback  # Import traceback

# Define excluded spaCy labels globally
EXCLUDED_SPACY_LABELS = {
    'ORG', 'WORK_OF_ART', 'FAC', 'PRODUCT', 'EVENT', 'LAW', 'LANGUAGE', 
    'PERCENT', 'MONEY' 
    # Excluded: QUANTITY, ORDINAL, CARDINAL
}

def generate_markdown(result: dict, output_md_path: str):
    """Generates a Markdown file summarizing and annotating the processed text,
       prioritizing gazetteer tags and excluding specific spaCy entity labels."""
    try:
        # --- Create Gazetteer Lookup with Priority ---
        gazetteer_tag_lookup = {}
        # Define priority: Lower index = higher priority. Add other types as needed.
        tag_type_priority = ['concept', 'topic', 'person', 'place', 'bible'] # 'bible' covers bible:person etc.

        for tag in result.get('tags', []):
            if ':' in tag:
                parts = tag.split(':', 1)
                tag_type_full = parts[0] # e.g., 'concept', 'person', 'bible'
                tag_value = parts[1].replace('_', ' ')
                lookup_key = tag_value.lower()

                # Determine base type for priority check (e.g., 'bible:person' -> 'bible')
                base_tag_type = tag_type_full.split(':')[0] 
                
                current_priority = tag_type_priority.index(base_tag_type) if base_tag_type in tag_type_priority else len(tag_type_priority)

                keys_to_update = [lookup_key]
                # --- Handle specific known mismatches ---
                if lookup_key == 'master':
                    keys_to_update.append('the master') # Ensure 'master' tag maps to 'the master' text
                # Add other mappings here if needed
                # --- End Handle specific mismatches ---

                for key in keys_to_update:
                    if key not in gazetteer_tag_lookup:
                        # Store tuple: (full_type, priority)
                        gazetteer_tag_lookup[key] = (tag_type_full, current_priority) 
                    else:
                        existing_type, existing_priority = gazetteer_tag_lookup[key]
                        # Only overwrite if new tag has higher priority (lower index)
                        if current_priority < existing_priority: 
                            gazetteer_tag_lookup[key] = (tag_type_full, current_priority)
        # ---------------------------------------------

        with open(output_md_path, 'w', encoding='utf-8') as f:
            # Sections 1, 2, 3 (Header, Tags, Bold/Italic) remain unchanged
            f.write(f"# {result.get('ref', 'Unknown Reference')}\n\n")
            f.write("## Tags\n\n")
            if result.get('tags'):
                for tag in sorted(result['tags']):
                    f.write(f"- {tag}\n")
            else:
                f.write("No tags generated.\n")
            f.write("\n")
            bold_italic_words = result.get('en_processed', {}).get('italicized_words', [])
            f.write("## Bolded & Italicized Words\n\n")
            if bold_italic_words:
                for word in bold_italic_words:
                    f.write(f"- {word}\n")
            else:
                f.write("No bolded and italicized words found.\n")
            f.write("\n")


            # 4. Annotated Text Section (Modified Annotation Logic)
            f.write("## Annotated Text (Bold Only)\n\n")
            doc = result.get('en_processed', {}).get('doc')
            if doc and doc.text:
                for sent in doc.sents:
                    original_sentence_text = sent.text
                    annotated_sentence_text = original_sentence_text
                    
                    entities_in_sentence = sorted([
                        (ent.start_char - sent.start_char, ent.end_char - sent.start_char, ent.text, ent.label_)
                        for ent in doc.ents if ent.start_char >= sent.start_char and ent.end_char <= sent.end_char
                    ], key=lambda x: x[1], reverse=True)

                    for start, end, text, spacy_label in entities_in_sentence:
                        if annotated_sentence_text[start:end] == text:
                            entity_text_lower = text.lower()
                            final_label = spacy_label # Default to spaCy label
                            from_gazetteer = False # Flag to track origin

                            # --- Prioritize Gazetteer Tag ---
                            if entity_text_lower in gazetteer_tag_lookup:
                                final_label = gazetteer_tag_lookup[entity_text_lower][0]
                                from_gazetteer = True
                            # ---------------------------------

                            # --- Exclude specific spaCy labels ---
                            # Only exclude if it's from spaCy AND in the exclusion list
                            if not from_gazetteer and final_label in EXCLUDED_SPACY_LABELS:
                                continue # Skip this entity
                            # -------------------------------------
                            
                            escaped_text = re.sub(r'([\\`*_{}[\]()#+.!-])', r'\\\1', text)
                            annotation = f"**{escaped_text}**`[{final_label}]`" 
                            annotated_sentence_text = annotated_sentence_text[:start] + annotation + annotated_sentence_text[end:]

                    f.write(annotated_sentence_text + "\n\n")
            else:
                f.write("No analyzed text available.\n")

    except Exception as e:
        # Use f-string for cleaner formatting
        print(f"Error generating Markdown file {output_md_path}: {e}")
        traceback.print_exc() # Add traceback for debugging


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
                # Keep the raw text with HTML for process_english
                en_text_raw = ' '.join(page_data.get('text', [])) if isinstance(page_data.get('text'), list) else page_data.get('text', '')
                he_text_raw = ' '.join(page_data.get('he', [])) if isinstance(page_data.get('he'), list) else page_data.get('he', '')

                # Clean only Hebrew text here (English cleaning happens inside process_english)
                # Note: clean_text now returns a tuple, but we only need the text for Hebrew here
                he_text_cleaned, _ = text_processor.clean_text(he_text_raw, 'he') 

                # 2. Process texts
                # Pass the raw English text to process_english
                en_processed = text_processor.process_english(en_text_raw) 
                he_processed = text_processor.process_hebrew(he_text_cleaned)

                # 3. Generate tags
                # Extract cleaned text for topic modeling if needed (or use doc directly)
                # cleaned_en_text_for_topics = en_processed['doc'].text # Example
                topics = [] # tagger.extract_topics([cleaned_en_text_for_topics])
                tags = tagger.generate_tags(en_processed, topics)

                # 4. Assemble result
                result = {
                    'ref': page_data.get('ref', f"{tractate}.{daf}"),
                    'en_text': en_text_raw, # Store raw text
                    'he_text': he_text_raw, # Store raw text
                    'en_processed': en_processed, 
                    'he_processed': he_processed,
                    'tags': tags
                }

                # Save results
                output_file = f"data/{tractate}_{daf}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    # Convert complex objects for JSON serialization
                    serializable_result = {}
                    serializable_result['ref'] = result['ref']
                    serializable_result['en_text'] = result['en_text'] # Raw text
                    serializable_result['he_text'] = result['he_text'] # Raw text
                    # Extract serializable parts from en_processed, including italics
                    serializable_result['en_processed'] = {
                        k: v for k, v in result['en_processed'].items()
                        if k in ['entities', 'noun_phrases', 'sentences', 'italicized_words'] # Add italicized_words
                    }
                    # Extract serializable parts from he_processed (e.g., embedding shape)
                    embedding_tensor = result['he_processed'].get('embeddings')
                    if embedding_tensor is not None:
                        serializable_result['he_processed'] = {'embedding_shape': list(embedding_tensor.shape)}
                    else:
                        serializable_result['he_processed'] = {'embedding_shape': None}

                    serializable_result['tags'] = result['tags']

                    json.dump(serializable_result, f, ensure_ascii=False, indent=2)

                print(f"Saved results to {output_file}")

                # Generate and Save Markdown results
                output_md_file = f"data/{tractate}_{daf}.md"
                generate_markdown(result, output_md_file)  # Call the new function
                print(f"Saved Markdown results to {output_md_file}")

                # Print tags and italics
                print(f"Tags: {', '.join(result['tags'])}")
                print(f"Italics: {', '.join(result['en_processed'].get('italicized_words', []))}\n" + "-" * 50)

            except Exception as e:
                # Print detailed error including traceback
                import traceback
                print(f"Error processing {tractate}.{daf}: {e}")
                traceback.print_exc()  # Print traceback for debugging
                print("-" * 50)

    print("Processing complete!")


if __name__ == "__main__":
    main()