"""
Main script for running the Talmud NLP Indexer.
"""
import json
import os
from typing import List
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

# Define term replacements for English text processing
TERM_REPLACEMENTS = {
    "Gemara": "Talmud",
    "Rabbi": "R'",
    "The Sages taught": "A baraita states",
    "Divine Voice": "bat kol",
    "Divine Presence": "Shekhina",
    "divine inspiration": "Holy Spirit",
    "Divine Spirit": "Holy Spirit",
    "the Lord": "YHWH",
    "leper": "metzora",
    "leprosy": "tzara'at",
    "phylacteries": "tefillin",
    "gentile": "non-Jew",
    "gentiles": "non-Jews",
    "ignoramus": "am ha'aretz",
    "maidservant": "female slave",
    "maidservants": "female slaves",
    "barrel": "jug",
    "barrels": "jugs",
    "the Holy One, Blessed be He": "God",
    "the Merciful One": "God",
    "the Almighty": "God",
    "engage in intercourse": "have sex",
    "engages in intercourse": "has sex",
    "engaged in intercourse": "had sex",
    "engaging in intercourse": "having sex",
    "had intercourse": "had sex",
    "intercourse with": "sex with",
    "Sages": "rabbis",
    "mishna": "Mishnah",
    "rainy season": "winter",
    "son of R'": "ben"
}

def apply_term_replacements(text: str) -> str:
    """Apply term replacements to English text for more consistent terminology."""
    if not text:
        return text
    
    # Apply replacements, being careful about word boundaries
    modified_text = text
    for old_term, new_term in TERM_REPLACEMENTS.items():
        # Use word boundaries for most replacements to avoid partial matches
        # Exception: some phrases don't need word boundaries
        if old_term in ["son of R'", "intercourse with"]:
            # These are phrase replacements that don't need word boundaries
            modified_text = modified_text.replace(old_term, new_term)
        else:
            # Use regex with word boundaries for single words and most phrases
            pattern = r'\b' + re.escape(old_term) + r'\b'
            modified_text = re.sub(pattern, new_term, modified_text, flags=re.IGNORECASE)
    
    return modified_text

def process_section(section: dict, text_processor, tagger) -> dict:
    """
    Process an individual section of Talmudic text.
    
    Args:
        section: Dictionary containing section data from Sefaria
        text_processor: TextProcessor instance
        tagger: TalmudTagger instance
        
    Returns:
        Dictionary containing processed section data
    """
    # Apply term replacements to English text
    en_text_processed = apply_term_replacements(section['en_text'])
    
    # Clean Hebrew text
    he_text_cleaned, _ = text_processor.clean_text(section['he_text'], 'he')
    
    # Process texts
    en_processed = text_processor.process_english(en_text_processed)
    he_processed = text_processor.process_hebrew(he_text_cleaned)
    
    # Generate tags for this section
    topics = []  # Could implement topic modeling per section if needed
    tags = tagger.generate_tags(en_processed, topics)
    
    return {
        'section_id': section['section_id'],
        'ref': section['ref'],
        'page_ref': section['page_ref'],
        'section_number': section['section_number'],
        'total_sections': section['total_sections'],
        'en_text_raw': section['en_text'],
        'en_text_processed': en_text_processed,
        'he_text_raw': section['he_text'],
        'he_text_cleaned': he_text_cleaned,
        'en_processed': en_processed,
        'he_processed': he_processed,
        'tags': tags
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

            # 3. Hebrew Text Section
            f.write("## Hebrew Text\n\n")
            he_text_raw = result.get('he_text', '')
            if he_text_raw:
                # Split Hebrew text into sentences based on punctuation
                # Clean the Hebrew text first (remove HTML tags but preserve structure)
                import re
                
                # Function to strip nikud (Hebrew vowel points)
                def strip_nikud(text):
                    # Hebrew nikud (vowel points) Unicode ranges:
                    # U+0591-U+05C7 (Hebrew accents and points)
                    # U+05D0-U+05EA are Hebrew letters (keep these)
                    # U+05F0-U+05F4 are Hebrew ligatures (keep these)
                    nikud_pattern = r'[\u0591-\u05C7]'
                    return re.sub(nikud_pattern, '', text)
                
                # Remove HTML tags but preserve the text
                he_text_cleaned = re.sub(r'<[^>]+>', '', he_text_raw)
                
                # Strip nikud from Hebrew text
                he_text_cleaned = strip_nikud(he_text_cleaned)
                
                # Split by common Hebrew punctuation marks and periods
                # Include both Hebrew and Latin punctuation
                he_sentences = re.split(r'[.!?׃։]', he_text_cleaned)
                
                # Clean and filter sentences
                he_sentences = [sent.strip() for sent in he_sentences if sent.strip()]
                
                # Generate Hebrew sentences with RTL formatting (no numbering)
                for sentence in he_sentences:
                    if sentence:  # Only process non-empty sentences
                        f.write(f"<div dir=\"rtl\">{sentence}</div>\n\n")
            else:
                f.write("No Hebrew text available.\n\n")

            # 4. Annotated English Text Section (Modified Annotation Logic)
            f.write("## Annotated English Text\n\n")
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
                            entity_text_lower = text.lower().strip('.:, ')
                            final_label = spacy_label # Default to spaCy label
                            from_gazetteer = False # Flag to track origin

                            # Apply same filtering logic as tagging.py
                            non_person_words = {
                                'lest', 'yhwh', 'lord', 'god', 'today', 'tomorrow', 'yesterday', 
                                'this', 'that', 'these', 'those', 'when', 'where', 'why', 'how',
                                'what', 'which', 'who', 'whom', 'whose', 'will', 'would', 'could',
                                'should', 'might', 'may', 'can', 'must', 'shall'
                            }
                            divine_names = {'yhwh', 'lord', 'god', 'hashem', 'adonai'}

                            # Skip filtered words for PERSON entities
                            if spacy_label == "PERSON":
                                if entity_text_lower in divine_names:
                                    final_label = f"concept:divine_name_{entity_text_lower}"
                                elif entity_text_lower in non_person_words:
                                    continue  # Skip this entity entirely
                            
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

def generate_sections_markdown(sections: List[dict], output_md_path: str):
    """
    Generate a Markdown file with section-aware analysis including full processing.
    
    Args:
        sections: List of processed section dictionaries
        output_md_path: Path to output markdown file
    """
    try:
        with open(output_md_path, 'w', encoding='utf-8') as f:
            # Page title - extract from first section's ref
            if sections:
                first_ref = sections[0]['ref']  # e.g. "Sanhedrin 91a:1"
                page_ref = first_ref.split(':')[0] if ':' in first_ref else first_ref  # e.g. "Sanhedrin 91a"
            else:
                page_ref = "Unknown"
            f.write(f"# {page_ref} (Section-Aware Analysis)\n\n")
            
            # Overall page tags (aggregate from all sections)
            all_tags = set()
            all_italics = set()
            
            for section in sections:
                all_tags.update(section['tags'])
                italics = section.get('en_processed', {}).get('italicized_words', [])
                all_italics.update(italics)
            
            # Write aggregated tags
            f.write("## Overall Page Tags\n\n")
            if all_tags:
                for tag in sorted(all_tags):
                    f.write(f"- {tag}\n")
            else:
                f.write("No tags found.\n")
            f.write("\n")
            
            # Write aggregated italics
            f.write("## Bolded & Italicized Words (All Sections)\n\n")
            if all_italics:
                for word in sorted(all_italics):
                    f.write(f"- {word}\n")
            else:
                f.write("No bolded and italicized words found.\n")
            f.write("\n")
            
            # Process each section with full analysis
            for section in sections:
                section_num = section['section_number']
                f.write(f"## Section {section_num}\n\n")
                
                # Section tags
                f.write(f"### Tags (Section {section_num})\n\n")
                section_tags = section['tags']
                if section_tags:
                    for tag in sorted(section_tags):
                        f.write(f"- {tag}\n")
                else:
                    f.write("No tags found in this section.\n")
                f.write("\n")
                
                # Hebrew text for this section
                f.write(f"### Hebrew Text (Section {section_num})\n\n")
                he_text_raw = section.get('he_text', section.get('he_text_cleaned', ''))
                if he_text_raw:
                    # Process Hebrew text (strip nikud, split sentences)
                    import re
                    
                    def strip_nikud(text):
                        nikud_pattern = r'[\u0591-\u05C7]'
                        return re.sub(nikud_pattern, '', text)
                    
                    he_text_cleaned = re.sub(r'<[^>]+>', '', he_text_raw)
                    he_text_cleaned = strip_nikud(he_text_cleaned)
                    he_sentences = re.split(r'[.!?׃։]', he_text_cleaned)
                    he_sentences = [sent.strip() for sent in he_sentences if sent.strip()]
                    
                    for sentence in he_sentences:
                        if sentence:
                            f.write(f"<div dir=\"rtl\">{sentence}</div>\n\n")
                else:
                    f.write("No Hebrew text available for this section.\n\n")
                
                # English text for this section with full annotation
                f.write(f"### Annotated English Text (Section {section_num})\n\n")
                
                # Create gazetteer lookup for this section
                from tagging import TalmudTagger
                tagger = TalmudTagger()
                gazetteer_tag_lookup = {}
                
                # Load gazetteers and create lookup
                gazetteer_sources = [
                    ('person:bible', tagger.bible_name_gazetteer),
                    ('place:bible', tagger.bible_place_gazetteer),
                    ('place:bible', tagger.bible_nation_gazetteer),  # Bible nations are also places
                    ('person', tagger.name_gazetteer),
                    ('place', tagger.toponym_gazetteer),
                    ('concept', tagger.concept_gazetteer)
                ]
                
                for tag_prefix, gazetteer in gazetteer_sources:
                    for word in gazetteer:
                        word_lower = word.lower()
                        if word_lower not in gazetteer_tag_lookup:
                            gazetteer_tag_lookup[word_lower] = (tag_prefix, word)
                
                doc = section.get('en_processed', {}).get('doc')
                if doc and doc.text:
                    # Helper function from tagging.py for multi-word matching
                    def find_term_in_text(term: str, text: str) -> bool:
                        """Helper to find a whole word, case-insensitive match for a term in text."""
                        escaped_term = re.escape(term)
                        pattern = r"\b" + escaped_term + r"\b"
                        return bool(re.search(pattern, text, re.IGNORECASE))
                    
                    for sent in doc.sents:
                        original_sentence_text = sent.text
                        annotated_sentence_text = original_sentence_text
                        covered_spans = set()  # Track which character spans are already annotated
                        
                        # First pass: Check for multi-word gazetteer matches
                        multi_word_matches = []
                        for tag_prefix, gazetteer in gazetteer_sources:
                            for gazetteer_term in gazetteer:
                                if ' ' in gazetteer_term and find_term_in_text(gazetteer_term, original_sentence_text):
                                    # Find the actual position of this multi-word term in the sentence
                                    escaped_term = re.escape(gazetteer_term)
                                    pattern = r"\b" + escaped_term + r"\b"
                                    match = re.search(pattern, original_sentence_text, re.IGNORECASE)
                                    if match:
                                        start_pos = match.start()
                                        end_pos = match.end()
                                        multi_word_matches.append((start_pos, end_pos, gazetteer_term, tag_prefix))
                        
                        # Sort by end position (reverse) to process from right to left
                        multi_word_matches.sort(key=lambda x: x[1], reverse=True)
                        
                        # Apply multi-word annotations
                        for start_pos, end_pos, term, tag_prefix in multi_word_matches:
                            # Check if this span overlaps with already covered spans
                            span_range = set(range(start_pos, end_pos))
                            if not span_range.intersection(covered_spans):
                                covered_spans.update(span_range)
                                escaped_text = re.sub(r'([`*_{}[\]()#+.!-])', r'\1', term)
                                annotation = f"**{escaped_text}**`[{tag_prefix}]`"
                                annotated_sentence_text = annotated_sentence_text[:start_pos] + annotation + annotated_sentence_text[end_pos:]
                        
                        # Second pass: Process individual spaCy entities (but skip covered spans)
                        entities_in_sentence = sorted([
                            (ent.start_char - sent.start_char, ent.end_char - sent.start_char, ent.text, ent.label_)
                            for ent in doc.ents if ent.start_char >= sent.start_char and ent.end_char <= sent.end_char
                        ], key=lambda x: x[1], reverse=True)

                        for start, end, text, spacy_label in entities_in_sentence:
                            # Check if this entity is already covered by multi-word annotation
                            entity_span = set(range(start, end))
                            if entity_span.intersection(covered_spans):
                                continue  # Skip already annotated spans
                                
                            if annotated_sentence_text[start:end] == text:
                                entity_text_lower = text.lower().strip('.:, ')
                                final_label = spacy_label
                                from_gazetteer = False

                                # Apply same filtering logic as tagging.py
                                non_person_words = {
                                    'lest', 'yhwh', 'lord', 'god', 'today', 'tomorrow', 'yesterday', 
                                    'this', 'that', 'these', 'those', 'when', 'where', 'why', 'how',
                                    'what', 'which', 'who', 'whom', 'whose', 'will', 'would', 'could',
                                    'should', 'might', 'may', 'can', 'must', 'shall'
                                }
                                divine_names = {'yhwh', 'lord', 'god', 'hashem', 'adonai'}

                                # Skip filtered words for PERSON entities
                                if spacy_label == "PERSON":
                                    if entity_text_lower in divine_names:
                                        final_label = f"concept:divine_name_{entity_text_lower}"
                                    elif entity_text_lower in non_person_words:
                                        continue  # Skip this entity entirely

                                # Prioritize Gazetteer Tag (single word lookup)
                                if entity_text_lower in gazetteer_tag_lookup:
                                    final_label = gazetteer_tag_lookup[entity_text_lower][0]
                                    from_gazetteer = True

                                # Exclude specific spaCy labels
                                if not from_gazetteer and final_label in EXCLUDED_SPACY_LABELS:
                                    continue
                                
                                escaped_text = re.sub(r'([`*_{}[\]()#+.!-])', r'\1', text)
                                annotation = f"**{escaped_text}**`[{final_label}]`" 
                                annotated_sentence_text = annotated_sentence_text[:start] + annotation + annotated_sentence_text[end:]

                        f.write(annotated_sentence_text + "\n\n")
                else:
                    f.write("No analyzed text available for this section.\n\n")
                
                # Section italics
                section_italics = section.get('en_processed', {}).get('italicized_words', [])
                if section_italics:
                    f.write(f"### Bolded & Italicized Words (Section {section_num})\n\n")
                    for word in sorted(section_italics):
                        f.write(f"- {word}\n")
                    f.write("\n")
                
                f.write("---\n\n")  # Section separator
                
    except Exception as e:
        print(f"Error generating sections Markdown file {output_md_path}: {e}")
        traceback.print_exc()


def main():
    """Run the Talmud NLP Indexer."""
    # Initialize components
    sefaria_api = SefariaAPI()
    text_processor = TextProcessor()
    tagger = TalmudTagger()

    # Define the target pages (Sanhedrin 90b-91a)
    tractate = "Sanhedrin"
    target_pages = ["90b", "91a"]  # Specific pages to process

    # Create directory for output
    os.makedirs("data", exist_ok=True)

    # Process each specific page
    for daf in target_pages:
        print(f"Processing {tractate}.{daf}...")

        try:
            # 1. Fetch data using section-aware approach
            sections_data = sefaria_api.fetch_talmud_page_sections(tractate, daf)
            print(f"  Found {len(sections_data)} sections for {tractate}.{daf}")

            # Process each section individually while aggregating page-level results
            page_sections = []
            page_en_texts = []
            page_he_texts = []
            all_page_tags = set()
            all_page_italics = set()

            for section in sections_data:
                section_num = section['section_number']
                print(f"    Processing section {section_num}/{len(sections_data)}...")

                # Get section texts
                en_text_raw = section['en_text']
                he_text_raw = section['he_text']

                # Skip empty sections
                if not en_text_raw.strip() and not he_text_raw.strip():
                    continue

                # Apply term replacements to English text before processing
                en_text_processed = apply_term_replacements(en_text_raw)

                # Store texts for page-level concatenation (for backward compatibility)
                page_en_texts.append(en_text_processed)
                page_he_texts.append(he_text_raw)

                # Clean Hebrew text for this section
                he_text_cleaned, _ = text_processor.clean_text(he_text_raw, 'he') 

                # 2. Process section texts
                en_processed = text_processor.process_english(en_text_processed) 
                he_processed = text_processor.process_hebrew(he_text_cleaned)

                # 3. Generate tags for this section
                topics = []  # Could be section-specific in the future
                section_tags = tagger.generate_tags(en_processed, topics)

                # Collect section-level data
                section_result = {
                    'section_id': section['section_id'],
                    'section_number': section['section_number'],
                    'ref': section['ref'],
                    'en_text': en_text_raw,
                    'en_text_processed': en_text_processed,
                    'he_text': he_text_raw,
                    'he_text_cleaned': he_text_cleaned,
                    'en_processed': en_processed,
                    'he_processed': he_processed,
                    'tags': section_tags
                }
                page_sections.append(section_result)

                # Aggregate tags and italics for page level
                all_page_tags.update(section_tags)
                all_page_italics.update(en_processed.get('italicized_words', []))

            # Create page-level concatenated texts for backward compatibility
            en_text_raw = ' '.join(page_en_texts)
            he_text_raw = ' '.join(page_he_texts)
            en_text_processed = ' '.join(page_en_texts)

            # Clean only Hebrew text here (English cleaning happens inside process_english)
            # Note: clean_text now returns a tuple, but we only need the text for Hebrew here
            he_text_cleaned, _ = text_processor.clean_text(he_text_raw, 'he')

            # 2. Process page-level texts (for backward compatibility)
            # Pass the processed English text (with term replacements) to process_english
            en_processed = text_processor.process_english(en_text_processed) 
            he_processed = text_processor.process_hebrew(he_text_cleaned)

            # 3. Generate page-level tags (combine all section tags)
            topics = [] # tagger.extract_topics([cleaned_en_text_for_topics])
            page_tags = list(all_page_tags)  # Convert set to list

            # Get page reference from first section
            page_ref = sections_data[0]['page_ref'] if sections_data else f"{tractate}.{daf}"

            # 4. Assemble result with section metadata
            result = {
                'ref': page_ref,
                'en_text': en_text_raw, # Store page-level concatenated text
                'en_text_processed': en_text_processed, # Store text with term replacements
                'he_text': he_text_raw, # Store page-level concatenated text
                'en_processed': en_processed, 
                'he_processed': he_processed,
                'tags': page_tags,  # Use aggregated page-level tags
                'sections': page_sections,  # NEW: Include all section data
                'section_count': len(sections_data)  # NEW: Section metadata
            }

            # Save results
            output_file = f"data/{tractate}_{daf}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                # Convert complex objects for JSON serialization
                serializable_result = {}
                serializable_result['ref'] = result['ref']
                serializable_result['en_text'] = result['en_text'] # Page-level concatenated text
                serializable_result['en_text_processed'] = result['en_text_processed'] # Text with term replacements
                serializable_result['he_text'] = result['he_text'] # Page-level concatenated text
                
                # Extract serializable parts from page-level en_processed, including italics
                serializable_result['en_processed'] = {
                    k: v for k, v in result['en_processed'].items()
                    if k in ['entities', 'noun_phrases', 'sentences', 'italicized_words']
                }
                
                # Extract serializable parts from page-level he_processed (e.g., embedding shape)
                embedding_tensor = result['he_processed'].get('embeddings')
                if embedding_tensor is not None:
                    serializable_result['he_processed'] = {'embedding_shape': list(embedding_tensor.shape)}
                else:
                    serializable_result['he_processed'] = {'embedding_shape': None}

                serializable_result['tags'] = result['tags']
                serializable_result['section_count'] = result['section_count']
                
                # NEW: Add serialized section data
                serializable_sections = []
                for section in result['sections']:
                    serializable_section = {
                        'section_id': section['section_id'],
                        'section_number': section['section_number'],
                        'ref': section['ref'],
                        'en_text': section['en_text'],
                        'en_text_processed': section['en_text_processed'],
                        'he_text': section['he_text'],
                        'he_text_cleaned': section['he_text_cleaned'],
                        'tags': section['tags']
                    }
                    
                    # Extract serializable parts from section en_processed
                    serializable_section['en_processed'] = {
                        k: v for k, v in section['en_processed'].items()
                        if k in ['entities', 'noun_phrases', 'sentences', 'italicized_words']
                    }
                    
                    # Extract serializable parts from section he_processed
                    section_embedding_tensor = section['he_processed'].get('embeddings')
                    if section_embedding_tensor is not None:
                        serializable_section['he_processed'] = {'embedding_shape': list(section_embedding_tensor.shape)}
                    else:
                        serializable_section['he_processed'] = {'embedding_shape': None}
                    
                    serializable_sections.append(serializable_section)
                
                serializable_result['sections'] = serializable_sections

                json.dump(serializable_result, f, ensure_ascii=False, indent=2)

            print(f"Saved results to {output_file}")

            # Generate and Save Markdown results
            output_md_file = f"data/{tractate}_{daf}.md"
            
            # Use section-aware markdown generation for better text flow
            output_sections_md_file = f"data/{tractate}_{daf}_sections.md"
            generate_sections_markdown(result['sections'], output_sections_md_file)
            print(f"Saved section-aware Markdown results to {output_sections_md_file}")
            
            # Also generate traditional concatenated markdown for backward compatibility
            generate_markdown(result, output_md_file)
            print(f"Saved traditional Markdown results to {output_md_file}")

            # Print tags and italics
            print(f"Total sections processed: {result['section_count']}")
            print(f"Page-level tags: {', '.join(result['tags'])}")
            print(f"Page-level italics: {', '.join(list(all_page_italics))}")
            print(f"Section breakdown:")
            for section in result['sections']:
                section_tags = ', '.join(section['tags'][:5])  # Show first 5 tags
                if len(section['tags']) > 5:
                    section_tags += f" ... (+{len(section['tags']) - 5} more)"
                print(f"  Section {section['section_number']}: {len(section['tags'])} tags ({section_tags})")
            print("-" * 50)

        except Exception as e:
            # Print detailed error including traceback
            import traceback
            print(f"Error processing {tractate}.{daf}: {e}")
            traceback.print_exc()  # Print traceback for debugging
            print("-" * 50)

    print("Processing complete!")


if __name__ == "__main__":
    main()