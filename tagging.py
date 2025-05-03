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
                 concept_gazetteer_path="data/talmud_concepts_gazetteer.txt",
                 bible_name_gazetteer_path="data/bible_names_gazetteer.txt"):  # Add bible name gazetteer path
        """Initialize the tagger and load the name, toponym, concept, and bible name gazetteers."""
        self.tag_categories = {
            "person": "Identifies individuals mentioned (e.g., Rabbis, historical figures).",
            "place": "Identifies geographical locations.",
            "concept": "Identifies key Talmudic or Jewish concepts.",
            "topic": "Identifies broader subjects or themes.",
            "halacha": "Tags related to Jewish law.",
            "aggadah": "Tags related to non-legalistic narrative or ethical content.",
            "person:bible": "Identifies biblical figures specifically."  # Add new category description
        }

        # Load name gazetteer
        self.name_gazetteer = self._load_gazetteer(name_gazetteer_path, "Name")
        # Load toponym gazetteer
        self.toponym_gazetteer = self._load_gazetteer(toponym_gazetteer_path, "Toponym")
        # Load concept gazetteer
        self.concept_gazetteer = self._load_gazetteer(concept_gazetteer_path, "Concept")
        # Load bible name gazetteer
        self.bible_name_gazetteer = self._load_gazetteer(bible_name_gazetteer_path, "Bible Name")  # Load the new gazetteer

        # Initialize scikit-learn components for topic modeling
        self.vectorizer = CountVectorizer(max_df=0.95, min_df=2, stop_words='english')
        self.lda = LatentDirichletAllocation(n_components=5, random_state=0)  # Default to 5 topics

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
        dtm = self.vectorizer.fit_transform(texts)
        self.lda.n_components = n_topics
        self.lda.fit(dtm)

        # Get feature names (words)
        feature_names = self.vectorizer.get_feature_names_out()

        # Extract top words for each topic
        topics = []
        for topic_idx, topic in enumerate(self.lda.components_):
            top_words_idx = topic.argsort()[:-10 - 1:-1]
            top_words = [feature_names[i] for i in top_words_idx]
            topics.append(top_words)

        return topics

    def generate_tags(self, processed_en: Dict[str, Any], topics: List[List[str]]) -> List[str]:
        """
        Generate tags based on processed English text, topics, and gazetteers.

        Args:
            processed_en: Dictionary containing processed English text data (must include 'doc', 'entities', 'noun_phrases')
            topics: List of topics (currently unused, placeholder for future integration)

        Returns:
            List of generated tags
        """
        tags = set()  # Use a set to automatically handle duplicates

        # Ensure required keys exist
        if 'doc' not in processed_en or not hasattr(processed_en['doc'], 'text'):
            print("Warning: 'doc' object with 'text' attribute not found in processed_en. Cannot perform text-based tagging.")
            text_content = ""  # Avoid errors later
        else:
            text_content = processed_en['doc'].text

        entities = processed_en.get('entities', [])
        noun_phrases = processed_en.get('noun_phrases', [])

        # 1. Extract entities from spaCy NER (if available)
        for ent_text, ent_label in entities:
            clean_ent = ent_text.lower().strip('.:, ')
            if not clean_ent:
                continue
            if ent_label == "PERSON":
                # Check if it's also a known Bible name first
                is_bible_name = False
                if self.bible_name_gazetteer:
                    for bible_name in self.bible_name_gazetteer:
                        if self._find_term_in_text(bible_name, ent_text):
                            clean_bible_name = bible_name.lower().strip('.:, ')
                            if clean_bible_name:
                                tags.add(f"person:bible:{clean_bible_name}")
                                is_bible_name = True
                                break
                if not is_bible_name:
                    tags.add(f"person:{clean_ent}")
            elif ent_label == "GPE" or ent_label == "LOC":
                tags.add(f"place:{clean_ent}")

        # 2. Check for keywords in noun phrases
        keywords = {"prayer", "blessings", "sabbath", "shabbat", "law", "halakha", "story", "aggadah"}
        potential_topic_tags = set()  # Store potential topic tags temporarily
        for phrase in noun_phrases:
            phrase_lower = phrase.lower()
            for keyword in keywords:
                if keyword in phrase_lower:
                    if keyword == "prayer":
                        potential_topic_tags.add("topic:prayer")
                    elif keyword == "blessings":  # Fix: Map blessings correctly
                        potential_topic_tags.add("topic:blessings")
                    elif keyword in {"law", "halakha"}:
                        potential_topic_tags.add("topic:halacha")
                    elif keyword in {"story", "aggadah"}:
                        potential_topic_tags.add("topic:aggadah")

        # 3. Match terms from gazetteers against the full text
        if text_content:
            # Match Bible Names FIRST
            if self.bible_name_gazetteer:
                for bible_name in self.bible_name_gazetteer:
                    if self._find_term_in_text(bible_name, text_content):
                        clean_bible_name = bible_name.lower().strip('.:, ')
                        if clean_bible_name:
                            tag_exists = False
                            for tag in tags:
                                if tag.startswith("person:") and tag.endswith(f":{clean_bible_name}"):
                                    tag_exists = True
                                    break
                            if not tag_exists:
                                tags.add(f"person:bible:{clean_bible_name}")

            # Match Names
            if self.name_gazetteer:
                for name in self.name_gazetteer:
                    if self._find_term_in_text(name, text_content):
                        clean_name = name.lower().strip('.:, ')
                        if clean_name:
                            if not any(t.endswith(f":{clean_name}") for t in tags if t.startswith("person:")):
                                tags.add(f"person:{clean_name}")

            # Match Toponyms
            if self.toponym_gazetteer:
                for toponym in self.toponym_gazetteer:
                    if self._find_term_in_text(toponym, text_content):
                        clean_toponym = toponym.lower().strip('.:, ')
                        if clean_toponym:
                            if f"place:{clean_toponym}" not in tags:
                                tags.add(f"place:{clean_toponym}")

            # Match Concepts
            if self.concept_gazetteer:
                for concept in self.concept_gazetteer:
                    if self._find_term_in_text(concept, text_content):
                        clean_concept = concept.lower().strip('.:, ')
                        if clean_concept:
                            tags.add(f"concept:{clean_concept}")

        # 4. Add potential topic tags from noun phrases, avoiding conflicts
        for topic_tag in potential_topic_tags:
            if topic_tag == "topic:shabbat":
                if "concept:shabbat" not in tags:
                    tags.add(topic_tag)
            else:
                tags.add(topic_tag)

        return sorted(list(tags))

    def _find_term_in_text(self, term: str, text: str) -> bool:
        """Helper to find a whole word, case-insensitive match for a term in text."""
        escaped_term = re.escape(term)
        pattern = r"\b" + escaped_term + r"\b"
        return bool(re.search(pattern, text, re.IGNORECASE))