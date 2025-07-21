"""
Text processing pipeline for Talmudic texts.
"""
import spacy
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from typing import Dict, Any, List, Optional, Tuple  # Updated import: Tuple for return type hint
import re  # Import the regex module
# Removed EntityRuler import


class TextProcessor:
    """Process and analyze Talmudic texts."""
    
    def __init__(self):
        """Initialize text processing components."""
        # Load English NLP model
        self.en_nlp = spacy.load("en_core_web_lg")

        # --- Removed EntityRuler code ---
        
        # Load Hebrew transformer model
        self.he_tokenizer = AutoTokenizer.from_pretrained("onlplab/alephbert-base")
        self.he_model = AutoModel.from_pretrained("onlplab/alephbert-base")
    
    def process_english(self, text: str) -> Dict[str, Any]:
        """
        Process English text using spaCy. Extracts italicized words first.
        
        Args:
            text: The raw English text (including HTML tags) to process
            
        Returns:
            Dictionary of processed data, including 'italicized_words'
        """
        # Clean text and extract italics first
        cleaned_text, italicized_words = self.clean_text(text, 'en')
        
        # Process the *cleaned* text with spaCy
        doc = self.en_nlp(cleaned_text)
        
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        noun_phrases = [chunk.text for chunk in doc.noun_chunks]
        sentences = [sent.text for sent in doc.sents]
        
        return {
            'entities': entities,
            'noun_phrases': noun_phrases,
            'sentences': sentences,
            'italicized_words': italicized_words,  # Add the extracted italics
            'doc': doc  # Keep the doc if needed downstream, though it's based on cleaned text
        }
    
    def process_hebrew(self, text: str) -> Dict[str, Any]:
        """
        Process Hebrew text using AlephBERT.
        
        Args:
            text: The Hebrew text to process
            
        Returns:
            Dictionary of processed data
        """
        tokens = self.he_tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        
        with torch.no_grad():
            outputs = self.he_model(**tokens)
        
        # Get embeddings from the last hidden state
        embeddings = outputs.last_hidden_state.mean(dim=1)
        
        return {
            'embeddings': embeddings,
            'tokens': tokens
        }
    
    def clean_text(self, text: str, language: str) -> Tuple[str, List[str]]:
        """
        Clean text and extract words that are both bolded and italicized for English.
        For English ('en'):
        - Extracts text within <b> tags for main processing (with all inner tags removed).
        - Separately extracts words found within <i> tags that are themselves inside <b> tags.
        For other languages, removes HTML tags.

        Args:
            text: The text to clean/process
            language: Language code ('en' or 'he')

        Returns:
            A tuple containing:
            - Cleaned text (content from <b> tags, inner tags removed)
            - List of unique words found within <i> tags nested inside <b> tags.
        """
        bold_italicized_words = []
        if language == 'en':
            # 1. Find all raw content within <b> tags
            bolded_parts_raw = re.findall(r'<b>(.*?)</b>', text, re.IGNORECASE | re.DOTALL)

            cleaned_bolded_parts_for_spacy = []

            for part in bolded_parts_raw:
                # 2. Find italics *within this specific bold part*
                italic_matches_in_bold = re.findall(r'<i>(.*?)</i>', part, re.IGNORECASE | re.DOTALL)
                for word in italic_matches_in_bold:
                    cleaned_word = word.strip()
                    # Basic cleaning for the italic word itself (remove potential stray tags if any)
                    cleaned_word = re.sub(r'<[^>]+>', '', cleaned_word).strip()
                    # Normalize by removing trailing punctuation before adding to list for deduplication
                    normalized_word = re.sub(r'[.,;:!?]$', '', cleaned_word).strip().lower()  # Remove trailing punctuation and lowercase
                    if normalized_word:
                        bold_italicized_words.append(normalized_word)

                # 3. Clean this bold part for spaCy (remove ALL inner tags)
                cleaned_part = re.sub(r'<[^>]+>', '', part)
                cleaned_part = cleaned_part.replace('\n', ' ').replace('\r', ' ').strip()
                if cleaned_part:
                    cleaned_bolded_parts_for_spacy.append(cleaned_part)

            # Join the cleaned bold parts for the main text processing
            cleaned_text = ' '.join(cleaned_bolded_parts_for_spacy)

            # Make the list of bold+italic words unique and sorted
            bold_italicized_words = sorted(list(set(bold_italicized_words)))

            return cleaned_text, bold_italicized_words
        else:
            # For Hebrew (or other languages), just remove HTML tags
            cleaned_text = re.sub(r'<[^>]+>', '', text)
            cleaned_text = cleaned_text.replace('\n', ' ').replace('\r', ' ')
            cleaned_text = cleaned_text.strip()
            # Return empty list for italics for non-English
            return cleaned_text, []