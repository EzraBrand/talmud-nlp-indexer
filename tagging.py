"""
Tag generation system for Talmudic texts.
"""
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from typing import Dict, Any, List, Optional


class TalmudTagger:
    """Generate and manage tags for Talmudic texts."""
    
    def __init__(self):
        """Initialize the tagger."""
        # Define tag categories
        self.tag_categories = {
            'topics': [],
            'people': [],
            'halacha': [],
            'aggadah': []
        }
    
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
    
    def generate_tags(self, processed_text: Dict[str, Any], topics: List[List[str]]) -> List[str]:
        """
        Generate tags based on processed text and topics.
        
        Args:
            processed_text: Dictionary containing processed text data
            topics: List of topics
            
        Returns:
            List of generated tags
        """
        tags = []
        
        # Extract entities for tagging
        if 'entities' in processed_text:
            for entity, label in processed_text['entities']:
                if label == 'PERSON':
                    tags.append(f"person:{entity.lower()}")
                elif label == 'GPE':
                    tags.append(f"place:{entity.lower()}")
        
        # Check for keywords in noun phrases
        if 'noun_phrases' in processed_text:
            for phrase in processed_text['noun_phrases']:
                phrase_lower = phrase.lower()
                # Example rules - would be expanded based on domain knowledge
                if 'prayer' in phrase_lower:
                    tags.append('topic:prayer')
                if 'blessing' in phrase_lower or 'berakhot' in phrase_lower:
                    tags.append('topic:blessings')
        
        # Deduplicate tags
        tags = list(set(tags))
        
        return tags