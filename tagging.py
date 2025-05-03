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
    
    def __init__(self, gazetteer_path="data/talmud_names_gazetteer.txt"):
        """Initialize the tagger and load the name gazetteer."""
        # Define tag categories
        self.tag_categories = {
            'topics': [],
            'people': [],
            'halacha': [],
            'aggadah': []
        }
        
        # Load name gazetteer
        self.name_gazetteer = set()
        try:
            if os.path.exists(gazetteer_path):
                with open(gazetteer_path, 'r', encoding='utf-8') as f:
                    self.name_gazetteer = {line.strip() for line in f if line.strip()}
                print(f"Loaded {len(self.name_gazetteer)} names from gazetteer: {gazetteer_path}")
            else:
                print(f"Warning: Gazetteer file not found at {gazetteer_path}. Proceeding without gazetteer.")
        except Exception as e:
            print(f"Error loading gazetteer file {gazetteer_path}: {e}. Proceeding without gazetteer.")
    
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
        Generate tags based on processed English text, topics, and gazetteer.
        
        Args:
            processed_en: Dictionary containing processed English text data (must include 'doc')
            topics: List of topics
            
        Returns:
            List of generated tags
        """
        tags = set()  # Use a set to automatically handle duplicates
        
        # Extract entities for tagging
        if 'entities' in processed_en:
            for entity, label in processed_en['entities']:
                if label == 'PERSON':
                    clean_entity = entity.lower().strip('.:, ')
                    if clean_entity:
                        tags.add(f"person:{clean_entity}")
                elif label == 'GPE':
                    clean_entity = entity.lower().strip('.:, ')
                    if clean_entity:
                        tags.add(f"place:{clean_entity}")
        
        # Check for keywords in noun phrases
        if 'noun_phrases' in processed_en:
            for phrase in processed_en['noun_phrases']:
                phrase_lower = phrase.lower()
                if 'prayer' in phrase_lower:
                    tags.add('topic:prayer')
                if 'blessing' in phrase_lower or 'berakhot' in phrase_lower:
                    tags.add('topic:blessings')
        
        # Match names from the gazetteer against the full text
        if 'doc' in processed_en and hasattr(processed_en['doc'], 'text'):
            text_content = processed_en['doc'].text
            if self.name_gazetteer:
                for name in self.name_gazetteer:
                    escaped_name = re.escape(name)
                    pattern = r"\b" + escaped_name + r"\b"
                    if re.search(pattern, text_content, re.IGNORECASE):
                        clean_name = name.lower().strip('.:, ')
                        if clean_name:
                            tags.add(f"person:{clean_name}")
            else:
                pass
        else:
            print("Warning: 'doc' object with 'text' attribute not found in processed_en. Cannot perform gazetteer matching.")
        
        return sorted(list(tags))