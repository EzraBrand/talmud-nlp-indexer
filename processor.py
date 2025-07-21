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
        
        # Define term replacements for text normalization
        self.term_replacements = {
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
    
    def apply_term_replacements(self, text: str) -> str:
        """
        Apply term replacements for text normalization.
        
        Args:
            text: The text to normalize
            
        Returns:
            Text with terms replaced according to the mapping
        """
        # Sort replacements by length (longest first) to avoid partial replacements
        sorted_replacements = sorted(self.term_replacements.items(), key=lambda x: len(x[0]), reverse=True)
        
        for old_term, new_term in sorted_replacements:
            # Use word boundaries to avoid partial word matches
            # This ensures "Rabbi" doesn't match within "Rabbinic"
            pattern = r'\b' + re.escape(old_term) + r'\b'
            text = re.sub(pattern, new_term, text, flags=re.IGNORECASE)
        
        return text
    
    def process_english(self, text: str) -> Dict[str, Any]:
        """
        Process English text using spaCy. Extracts italicized words first, 
        applies term replacements, then processes with spaCy.
        
        Args:
            text: The raw English text (including HTML tags) to process
            
        Returns:
            Dictionary of processed data, including 'italicized_words'
        """
        # Clean text and extract italics first
        cleaned_text, italicized_words = self.clean_text(text, 'en')
        
        # Apply term replacements for normalization
        normalized_text = self.apply_term_replacements(cleaned_text)
        
        # Process the normalized text with spaCy
        doc = self.en_nlp(normalized_text)
        
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        noun_phrases = [chunk.text for chunk in doc.noun_chunks]
        sentences = [sent.text for sent in doc.sents]
        
        return {
            'entities': entities,
            'noun_phrases': noun_phrases,
            'sentences': sentences,
            'italicized_words': italicized_words,  # Add the extracted italics
            'doc': doc,  # Keep the doc if needed downstream, based on normalized text
            'normalized_text': normalized_text  # Store the normalized text for reference
        }
    
    def process_hebrew(self, text: str) -> Dict[str, Any]:
        """
        Process Hebrew text using AlephBERT and split into sentences.
        
        Args:
            text: The Hebrew text to process
            
        Returns:
            Dictionary of processed data including sentences
        """
        tokens = self.he_tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        
        with torch.no_grad():
            outputs = self.he_model(**tokens)
        
        # Get embeddings from the last hidden state
        embeddings = outputs.last_hidden_state.mean(dim=1)
        
        # Split into sentences and remove nikud
        sentences = self.split_hebrew_sentences(text)
        sentences_without_nikud = [self.remove_nikud(sentence) for sentence in sentences]
        
        return {
            'embeddings': embeddings,
            'tokens': tokens,
            'sentences': sentences,
            'sentences_without_nikud': sentences_without_nikud
        }
    
    def split_hebrew_sentences(self, text: str) -> List[str]:
        """
        Split Hebrew text into sentences based on punctuation.
        
        Args:
            text: The Hebrew text to split
            
        Returns:
            List of Hebrew sentences
        """
        if not text:
            return []
        
        # Hebrew sentence ending punctuation marks
        # Including period, question mark, exclamation mark, colon, semicolon
        sentence_endings = r'[.!?:;]'
        
        # Split on sentence endings but keep the punctuation
        sentences = re.split(f'({sentence_endings})', text)
        
        # Reconstruct sentences with their punctuation
        result_sentences = []
        for i in range(0, len(sentences), 2):
            sentence = sentences[i].strip()
            if i + 1 < len(sentences):
                sentence += sentences[i + 1]  # Add the punctuation back
            
            if sentence:  # Only add non-empty sentences
                result_sentences.append(sentence.strip())
        
        # If no punctuation-based splits were found, return the whole text as one sentence
        if not result_sentences and text.strip():
            result_sentences = [text.strip()]
        
        return result_sentences
    
    def remove_nikud(self, text: str) -> str:
        """
        Remove nikud (diacritical marks) from Hebrew text.
        
        Args:
            text: Hebrew text with nikud
            
        Returns:
            Hebrew text without nikud
        """
        if not text:
            return text
        
        # Unicode ranges for Hebrew nikud (diacritical marks)
        # Hebrew points: U+05B0 to U+05BD, U+05BF, U+05C1, U+05C2, U+05C4, U+05C5, U+05C7
        nikud_pattern = r'[\u05B0-\u05BD\u05BF\u05C1\u05C2\u05C4\u05C5\u05C7]'
        
        # Remove nikud marks
        text_without_nikud = re.sub(nikud_pattern, '', text)
        
        return text_without_nikud
    
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