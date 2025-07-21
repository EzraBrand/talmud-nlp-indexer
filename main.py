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
    """Generates a Markdown file with Hebrew and English text sections,
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

        # Get the processed data
        doc = result.get('en_processed', {}).get('doc')
        hebrew_sentences = result.get('he_processed', {}).get('sentences_without_nikud', [])

        with open(output_md_path, 'w', encoding='utf-8') as f:
            # Header
            f.write(f"# {result.get('ref', 'Unknown Reference')}\n\n")
            
            # Tags
            f.write("## Tags\n\n")
            if result.get('tags'):
                for tag in sorted(result['tags']):
                    f.write(f"- {tag}\n")
            else:
                f.write("No tags generated.\n")
            f.write("\n")
            
            # Bold/Italic words
            bold_italic_words = result.get('en_processed', {}).get('italicized_words', [])
            f.write("## Bolded & Italicized Words\n\n")
            if bold_italic_words:
                for word in bold_italic_words:
                    f.write(f"- {word}\n")
            else:
                f.write("No bolded and italicized words found.\n")
            f.write("\n")

            # Hebrew Text
            f.write("## Hebrew Text\n\n")
            if hebrew_sentences:
                for i, sentence in enumerate(hebrew_sentences, 1):
                    f.write(f"{i}. <div dir=\"rtl\">**{sentence}**</div>\n\n")
            else:
                f.write("No Hebrew sentences found.\n\n")

            # Annotated English Text
            f.write("## Annotated English Text\n\n")
            if doc:
                # Create a copy of the text to annotate
                annotated_text = doc.text
                
                # Collect entities and sort by end position (reverse order for replacement)
                entities = [(ent.start_char, ent.end_char, ent.text, ent.label_) for ent in doc.ents]
                entities.sort(key=lambda x: x[1], reverse=True)
                
                # Apply annotations
                for start, end, text, spacy_label in entities:
                    if start >= 0 and end <= len(annotated_text) and annotated_text[start:end] == text:
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
                        
                        import re
                        escaped_text = re.sub(r'([\\`*_{}[\]()#+.!-])', r'\\\1', text)
                        annotation = f"**{escaped_text}**`[{final_label}]`" 
                        annotated_text = annotated_text[:start] + annotation + annotated_text[end:]
                
                f.write(annotated_text + "\n\n")
            else:
                f.write("No English text processed.\n\n")

    except Exception as e:
        # Use f-string for cleaner formatting
        print(f"Error generating Markdown file {output_md_path}: {e}")
        import traceback
        traceback.print_exc() # Add traceback for debugging

    except Exception as e:
        # Use f-string for cleaner formatting
        print(f"Error generating Markdown file {output_md_path}: {e}")
        import traceback
        traceback.print_exc() # Add traceback for debugging


def main():
    """Run the Talmud NLP Indexer."""
    # Initialize components
    sefaria_api = SefariaAPI()
    text_processor = TextProcessor()
    tagger = TalmudTagger()

    # Define the target pages (testing Sanhedrin 90b-91a)
    tractate = "Sanhedrin"
    start_daf = "90b"  # Starting from 90b
    end_daf = "91a"    # Ending at 91a

    # Create directory for output
    os.makedirs("data", exist_ok=True)

    # Fetch the range of pages
    try:
        pages_data = sefaria_api.fetch_tractate_range(tractate, start_daf, end_daf)
        print(f"Fetched {len(pages_data)} pages from {tractate} {start_daf}-{end_daf}")
    except Exception as e:
        print(f"Error fetching range: {e}")
        return

    # Process each page
    for page_data in pages_data:
        # Extract the daf reference from the page data
        ref = page_data.get('ref', '')
        daf = ref.split('.')[-1] if '.' in ref else ref.replace(tractate + ' ', '')
        print(f"Processing {tractate}.{daf}...")

        try:
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
                # Extract serializable parts from en_processed, including italics and normalized text
                serializable_result['en_processed'] = {
                    k: v for k, v in result['en_processed'].items()
                    if k in ['entities', 'noun_phrases', 'sentences', 'italicized_words', 'normalized_text'] # Add normalized_text
                }
                # Extract serializable parts from he_processed (e.g., embedding shape and sentences)
                embedding_tensor = result['he_processed'].get('embeddings')
                he_processed_data = {}
                if embedding_tensor is not None:
                    he_processed_data['embedding_shape'] = list(embedding_tensor.shape)
                else:
                    he_processed_data['embedding_shape'] = None
                
                # Add Hebrew sentences
                he_processed_data['sentences'] = result['he_processed'].get('sentences', [])
                he_processed_data['sentences_without_nikud'] = result['he_processed'].get('sentences_without_nikud', [])
                serializable_result['he_processed'] = he_processed_data

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