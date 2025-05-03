"""
Text processing pipeline for Talmudic texts.
"""
import spacy
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from typing import Dict, Any, List, Optional


class TextProcessor:
    """Process and analyze Talmudic texts."""
    
    def __init__(self):
        """Initialize text processing components."""
        # Load English NLP model
        self.en_nlp = spacy.load("en_core_web_lg")
        
        # Load Hebrew transformer model
        self.he_tokenizer = AutoTokenizer.from_pretrained("onlplab/alephbert-base")
        self.he_model = AutoModel.from_pretrained("onlplab/alephbert-base")
    
    def process_english(self, text: str) -> Dict[str, Any]:
        """
        Process English text using spaCy.
        
        Args:
            text: The English text to process
            
        Returns:
            Dictionary of processed data
        """
        doc = self.en_nlp(text)
        
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        noun_phrases = [chunk.text for chunk in doc.noun_chunks]
        
        # Extract key sentences
        sentences = [sent.text for sent in doc.sents]
        
        return {
            'entities': entities,
            'noun_phrases': noun_phrases,
            'sentences': sentences,
            'doc': doc
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
    
    def clean_text(self, text: str, language: str) -> str:
        """
        Clean and normalize text.
        
        Args:
            text: The text to clean
            language: Language code ('en' or 'he')
            
        Returns:
            Cleaned text
        """
        # Basic cleaning applicable to both languages
        text = text.replace('\n', ' ').replace('\r', ' ')
        
        # Language-specific cleaning
        if language == 'en':
            # Example English-specific cleaning
            pass
        elif language == 'he':
            # Example Hebrew-specific cleaning
            pass
        
        return text