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
                 bible_name_gazetteer_path="data/bible_names_gazetteer.txt",
                 bible_place_gazetteer_path="data/bible_places_gazetteer.txt",  # Add bible place gazetteer path
                 bible_nation_gazetteer_path="data/bible_nations_gazetteer.txt"):  # Add bible nation gazetteer path
        """Initialize the tagger and load all gazetteers."""
        self.tag_categories = {
            "person": "Identifies individuals mentioned (e.g., Rabbis, historical figures).",
            "place": "Identifies geographical locations.",
            "concept": "Identifies key Talmudic or Jewish concepts.",
            "topic": "Identifies broader subjects or themes.",
            "halacha": "Tags related to Jewish law.",
            "aggadah": "Tags related to non-legalistic narrative or ethical content.",
            "person:bible": "Identifies biblical figures specifically.",
            "place:bible": "Identifies biblical places or nations specifically."  # Add new category description
        }

        # Load name gazetteer
        self.name_gazetteer = self._load_gazetteer(name_gazetteer_path, "Name")
        # Load toponym gazetteer
        self.toponym_gazetteer = self._load_gazetteer(toponym_gazetteer_path, "Toponym")
        # Load concept gazetteer
        self.concept_gazetteer = self._load_gazetteer(concept_gazetteer_path, "Concept")
        # Load bible name gazetteer
        self.bible_name_gazetteer = self._load_gazetteer(bible_name_gazetteer_path, "Bible Name")
        # Load bible place gazetteer
        self.bible_place_gazetteer = self._load_gazetteer(bible_place_gazetteer_path, "Bible Place")  # Load the new gazetteer
        # Load bible nation gazetteer
        self.bible_nation_gazetteer = self._load_gazetteer(bible_nation_gazetteer_path, "Bible Nation")  # Load the new gazetteer

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

    def generate_tags(self, processed_en: Dict[str, Any], topics: Optional[List[List[str]]] = None) -> List[str]:
        """
        Generate tags from text using spaCy NER, gazetteers, and topic modeling.

        Args:
            processed_en: Processed English text with entities and noun phrases
            topics: Optional topic modeling results

        Returns:
            List of generated tags
        """
        tags = set()  # Use a set to automatically handle duplicates
        tags_to_remove = set()  # Keep track of less specific tags to remove

        # Ensure required keys exist
        if 'doc' not in processed_en or not hasattr(processed_en['doc'], 'text'):
            print("Warning: 'doc' object with 'text' attribute not found in processed_en. Cannot perform text-based tagging.")
            text_content = ""  # Avoid errors later
        else:
            text_content = processed_en['doc'].text

        entities = processed_en.get('entities', [])
        noun_phrases = processed_en.get('noun_phrases', [])

        # Define words that should never be tagged as persons (common misclassifications)
        non_person_words = {
            'lest', 'yhwh', 'lord', 'god', 'today', 'tomorrow', 'yesterday', 
            'this', 'that', 'these', 'those', 'when', 'where', 'why', 'how',
            'what', 'which', 'who', 'whom', 'whose', 'will', 'would', 'could',
            'should', 'might', 'may', 'can', 'must', 'shall'
        }

        # Special handling for divine names
        divine_names = {'yhwh', 'lord', 'god', 'hashem', 'adonai'}

        # 1. Extract entities from spaCy NER (with improved filtering)
        for ent_text, ent_label in entities:
            clean_ent = ent_text.lower().strip('.:, ')
            if not clean_ent:
                continue

            if ent_label == "PERSON":
                # Handle divine names specially
                if clean_ent in divine_names:
                    tags.add(f"concept:divine_name_{clean_ent}")
                    continue
                    
                # Skip obvious non-person words
                if clean_ent in non_person_words:
                    continue
                    
                # Check if it's in any place gazetteer first (prioritize place over person for ambiguous terms)
                is_known_place = False
                all_place_gazetteers = self.toponym_gazetteer.union(self.bible_place_gazetteer).union(self.bible_nation_gazetteer)
                if all_place_gazetteers:
                    for place_name in all_place_gazetteers:
                        if self._find_term_in_text(place_name, ent_text):
                            # This entity is actually a known place, skip adding as person
                            is_known_place = True
                            break
                
                if not is_known_place:
                    # Check if it's also a known Bible name first
                    is_bible_name = False
                    if self.bible_name_gazetteer:
                        for bible_name in self.bible_name_gazetteer:
                            # Use _find_term_in_text for robust matching (whole word, case-insensitive)
                            if self._find_term_in_text(bible_name, ent_text):
                                clean_bible_name = bible_name.lower().strip('.:, ')
                                if clean_bible_name:
                                    tags.add(f"person:bible:{clean_bible_name}")
                                    is_bible_name = True
                                    break  # Found a match, no need to check further bible names for this entity
                    if not is_bible_name:
                        tags.add(f"person:{clean_ent}")

            elif ent_label == "GPE" or ent_label == "LOC":
                # Check if it's a known person name first to avoid misclassification
                is_known_person = False
                if self.name_gazetteer and self._find_term_in_text(ent_text, ent_text): # Check against name gazetteer
                     # Check if the term itself is in the name gazetteer
                     clean_name_check = ent_text.lower().strip('. :,')
                     if clean_name_check and clean_name_check in {name.lower().strip('. :,') for name in self.name_gazetteer}:
                         is_known_person = True
                if not is_known_person and self.bible_name_gazetteer and self._find_term_in_text(ent_text, ent_text): # Check against bible name gazetteer
                     clean_bible_name_check = ent_text.lower().strip('. :,')
                     if clean_bible_name_check and clean_bible_name_check in {name.lower().strip('. :,') for name in self.bible_name_gazetteer}:
                         is_known_person = True

                if not is_known_person:
                    # Check if it's also a known Bible place/nation first
                    is_bible_place_or_nation = False
                    # Combine bible place and nation gazetteers for checking
                    bible_locations = self.bible_place_gazetteer.union(self.bible_nation_gazetteer)
                    if bible_locations:
                        for bible_loc in bible_locations:
                            # Use _find_term_in_text for robust matching
                            if self._find_term_in_text(bible_loc, ent_text):
                                clean_bible_loc = bible_loc.lower().strip('. :,')
                                if clean_bible_loc:
                                    tags.add(f"place:bible:{clean_bible_loc}")
                                    is_bible_place_or_nation = True
                                    break  # Found a match
                    if not is_bible_place_or_nation:
                        tags.add(f"place:{clean_ent}")

        # 2. Check for keywords in noun phrases (Topic/Halacha/Aggadah - Basic)
        keywords = {"prayer", "blessings", "sabbath", "shabbat", "law", "halakha", "story", "aggadah"}
        potential_topic_tags = set()
        for phrase in noun_phrases:
            phrase_lower = phrase.lower()
            for keyword in keywords:
                if keyword in phrase_lower:  # Simple substring check for now
                    if keyword == "prayer":
                        potential_topic_tags.add("topic:prayer")
                    elif keyword == "blessings":
                        potential_topic_tags.add("topic:blessings")
                    elif keyword in {"law", "halakha"}:
                        potential_topic_tags.add("topic:halacha")
                    elif keyword in {"story", "aggadah"}:
                        potential_topic_tags.add("topic:aggadah")
                    elif keyword == "shabbat":
                        potential_topic_tags.add("topic:shabbat")  # Keep shabbat separate for now

        # 3. Match terms from gazetteers against the full text (more comprehensive check)
        if text_content:
            # --- Bible Names (Prioritize) ---
            if self.bible_name_gazetteer:
                for bible_name in self.bible_name_gazetteer:
                    if self._find_term_in_text(bible_name, text_content):
                        clean_bible_name = bible_name.lower().strip('.:, ')
                        if clean_bible_name:
                            # Add bible tag if no specific bible tag exists yet
                            if not any(t == f"person:bible:{clean_bible_name}" for t in tags):
                                tags.add(f"person:bible:{clean_bible_name}")
                            # Mark regular person tag for removal if it exists
                            regular_tag = f"person:{clean_bible_name}"
                            if regular_tag in tags:
                                tags_to_remove.add(regular_tag)

            # --- Bible Places/Nations (Prioritize) ---
            bible_locations = self.bible_place_gazetteer.union(self.bible_nation_gazetteer)
            if bible_locations:
                for bible_loc in bible_locations:
                    if self._find_term_in_text(bible_loc, text_content):
                        clean_bible_loc = bible_loc.lower().strip('.:, ')
                        if clean_bible_loc:
                            # Add bible tag if no specific bible tag exists yet
                            if not any(t == f"place:bible:{clean_bible_loc}" for t in tags):
                                tags.add(f"place:bible:{clean_bible_loc}")
                            # Mark regular place tag for removal if it exists
                            regular_tag = f"place:{clean_bible_loc}"
                            if regular_tag in tags:
                                tags_to_remove.add(regular_tag)

            # --- Talmud Names ---
            if self.name_gazetteer:
                for name in self.name_gazetteer:
                    if self._find_term_in_text(name, text_content):
                        clean_name = name.lower().strip('.:, ')
                        if clean_name:
                            # Add only if no person tag (regular or bible) exists for this name
                            if not any(t.startswith("person:") and t.endswith(f":{clean_name}") for t in tags):
                                tags.add(f"person:{clean_name}")

            # --- Talmud Toponyms ---
            if self.toponym_gazetteer:
                for toponym in self.toponym_gazetteer:
                    if self._find_term_in_text(toponym, text_content):
                        clean_toponym = toponym.lower().strip('.:, ')
                        if clean_toponym:
                            # Add only if no place tag (regular or bible) exists for this place
                            if not any(t.startswith("place:") and t.endswith(f":{clean_toponym}") for t in tags):
                                tags.add(f"place:{clean_toponym}")

            # --- Concepts ---
            if self.concept_gazetteer:
                for concept in self.concept_gazetteer:
                    if self._find_term_in_text(concept, text_content):
                        clean_concept = concept.lower().strip('.:, ')
                        if clean_concept:
                            tags.add(f"concept:{clean_concept}")  # Concepts don't usually overlap like names/places

        # 4. Remove less specific tags marked for removal
        tags.difference_update(tags_to_remove)

        # 5. Add potential topic tags from noun phrases, avoiding conflicts
        for topic_tag in potential_topic_tags:
            # Example conflict check: don't add topic:shabbat if concept:shabbat exists
            if topic_tag == "topic:shabbat":
                if "concept:shabbat" not in tags:
                    tags.add(topic_tag)
            # Add other topic tags directly for now
            elif topic_tag in {"topic:prayer", "topic:blessings", "topic:halacha", "topic:aggadah"}:
                tags.add(topic_tag)

        # 6. Add tags from topic modeling (if topics were provided)
        if topics:
            for topic_words in topics:
                if topic_words:  # Ensure the topic list is not empty
                    top_word = topic_words[0]  # Take the most significant word
                    tags.add(f"topic:{top_word}")

        return sorted(list(tags))

    def _find_term_in_text(self, term: str, text: str) -> bool:
        """Helper to find a whole word, case-insensitive match for a term in text."""
        escaped_term = re.escape(term)
        pattern = r"\b" + escaped_term + r"\b"
        return bool(re.search(pattern, text, re.IGNORECASE))