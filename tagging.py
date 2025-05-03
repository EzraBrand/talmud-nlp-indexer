"""
Tag generation system for Talmudic texts.
"""
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from typing import Dict, Any, List, Optional
import os  # For file path operations
import re  # For regex matching


class TalmudTagger:
    """Generate and manage tags for Talmudic texts."""
    
    def __init__(self, 
                 name_gazetteer_path="data/talmud_names_gazetteer.txt",
                 toponym_gazetteer_path="data/talmud_toponyms_gazetteer.txt",
                 concept_gazetteer_path="data/talmud_concepts_gazetteer.txt"):
        """Initialize the tagger and load the name, toponym, and concept gazetteers."""
        # Define tag categories
        self.tag_categories = {
            'topics': [],
            'people': [],
            'halacha': [],
            'aggadah': []
        }
        
        # Load name gazetteer
        self.name_gazetteer = self._load_gazetteer(name_gazetteer_path, "Name")
        # Load toponym gazetteer
        self.toponym_gazetteer = self._load_gazetteer(toponym_gazetteer_path, "Toponym")
        # Load concept gazetteer
        self.concept_gazetteer = self._load_gazetteer(concept_gazetteer_path, "Concept")

    def _load_gazetteer(self, gazetteer_path: str, gazetteer_type: str) -> set:
        """Helper function to load a gazetteer file into a set."""
        gazetteer_set = set()
        try:
            if os.path.exists(gazetteer_path):
                with open(gazetteer_path, 'r', encoding='utf-8') as f:
                    gazetteer_set = {line.strip() for line in f if line.strip()}
                print(f"Loaded {len(gazetteer_set)} {gazetteer_type.lower()}s from gazetteer: {gazetteer_path}")
            else:
                print(f"Warning: {gazetteer_type} gazetteer file not found at {gazetteer_path}. Proceeding without it.")
        except Exception as e:
            print(f"Error loading {gazetteer_type.lower()} gazetteer file {gazetteer_path}: {e}. Proceeding without it.")
        return gazetteer_set
    
    def extract_topics(self, texts: List[str], n_topics: int = 5) -> List[List[str]]:
        """
        Extract main topics from a collection of texts.
        
        Args:
            texts: List of text documents
            n_topics: Number of topics to extract
            
        Returns:
            List of topics, each containing top words
        """
        vectorizer = CountVectorizer(max_df=0.95, min_df=2, stop_words='english')
        dtm = vectorizer.fit_transform(texts)
        
        lda = LatentDirichletAllocation(n_components=n_topics, random_state=42)
        lda.fit(dtm)
        
        # Get feature names (words)
        feature_names = vectorizer.get_feature_names_out()
        
        # Extract top words for each topic
        topics = []
        for topic_idx, topic in enumerate(lda.components_):
            top_words_idx = topic.argsort()[:-10 - 1:-1]
            top_words = [feature_names[i] for i in top_words_idx]
            topics.append(top_words)
            
        return topics
    
    def generate_tags(self, processed_en: Dict[str, Any], topics: List[List[str]]) -> List[str]:
        """
        Generate tags based on processed English text, topics, and gazetteers.
        
        Args:
            processed_en: Dictionary containing processed English text data (must include 'doc')
            topics: List of topics (currently unused, placeholder)
            
        Returns:
            List of generated tags
        """
        tags = set()  # Use a set to automatically handle duplicates
        
        # Extract entities for tagging
        if 'entities' in processed_en:
            for entity, label in processed_en['entities']:
                clean_entity = entity.lower().strip('.:, ')
                if not clean_entity:
                    continue  # Skip empty entities
                
                if label == 'PERSON':
                    tags.add(f"person:{clean_entity}")
                elif label == 'GPE':  # Geographical Political Entity
                    tags.add(f"place:{clean_entity}")
        
        # Check for keywords in noun phrases
        if 'noun_phrases' in processed_en:
            for phrase in processed_en['noun_phrases']:
                phrase_lower = phrase.lower()
                if 'prayer' in phrase_lower:
                    tags.add('topic:prayer')
                if 'blessing' in phrase_lower or 'berakhot' in phrase_lower:
                    tags.add('topic:blessings')
        
        # Match terms from gazetteers against the full text
        if 'doc' in processed_en and hasattr(processed_en['doc'], 'text'):
            text_content = processed_en['doc'].text
            
            # Match Names
            if self.name_gazetteer:
                for name in self.name_gazetteer:
                    if self._find_term_in_text(name, text_content):
                        clean_name = name.lower().strip('.:, ')
                        if clean_name:
                            tags.add(f"person:{clean_name}")
            
            # Match Toponyms
            if self.toponym_gazetteer:
                for toponym in self.toponym_gazetteer:
                    if self._find_term_in_text(toponym, text_content):
                        clean_toponym = toponym.lower().strip('.:, ')
                        if clean_toponym:
                            tags.add(f"place:{clean_toponym}")
                            
            # Match Concepts
            if self.concept_gazetteer:
                for concept in self.concept_gazetteer:
                    if self._find_term_in_text(concept, text_content):
                        clean_concept = concept.lower().strip('.:, ')
                        if clean_concept:
                            tags.add(f"concept:{clean_concept}")
        else:
            print("Warning: 'doc' object with 'text' attribute not found in processed_en. Cannot perform gazetteer matching.")
        
        return sorted(list(tags))

    def _find_term_in_text(self, term: str, text: str) -> bool:
        """Helper to find a whole word, case-insensitive match for a term in text."""
        escaped_term = re.escape(term)
        pattern = r"\b" + escaped_term + r"\b"
        return bool(re.search(pattern, text, re.IGNORECASE))