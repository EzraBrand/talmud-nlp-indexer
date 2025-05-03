# tests/test_tagging.py
import pytest
from tagging import TalmudTagger
import numpy as np # Needed for mock LDA components
from unittest.mock import mock_open, MagicMock # Import mock_open and MagicMock

# Mock scikit-learn components
class MockVectorizer:
    def fit_transform(self, texts):
        # Return a dummy document-term matrix (sparse matrix often used, but dense is fine for mock)
        # Shape: (n_documents, n_features)
        return np.array([[1, 1, 0], [0, 1, 1]]) # Example for 2 docs, 3 features

    def get_feature_names_out(self):
        # Return dummy feature names
        return np.array(["word1", "word2", "word3"])

class MockLDA:
    def __init__(self, n_components, random_state):
        self.n_components = n_components
        # Dummy components_ attribute: shape (n_topics, n_features)
        # Values represent word weights for each topic
        self.components_ = np.array([[0.1, 0.8, 0.1], [0.5, 0.1, 0.4]]) # Example for 2 topics

    def fit(self, dtm):
        # Mock fit method, doesn't need to do anything
        pass

# Mock spaCy Doc object needed for gazetteer matching
class MockProcessedDoc:
    def __init__(self, text):
        self.text = text

@pytest.fixture
def tagger(mocker): # Add mocker to the fixture
    """Fixture to create a TalmudTagger instance with mocked sklearn and gazetteer."""
    # Mock scikit-learn components
    mocker.patch('tagging.CountVectorizer', return_value=MockVectorizer())
    mocker.patch('tagging.LatentDirichletAllocation', side_effect=lambda n_components, random_state: MockLDA(n_components, random_state))
    
    # Mock the gazetteer file reading
    gazetteer_content = "Rabbi Akiva\nRav Ashi\nShimon ben Lakish\nZutra bar Toviyya"
    # Mock os.path.exists to return True for the gazetteer path
    mocker.patch('tagging.os.path.exists', return_value=True)
    # Mock builtins.open to simulate reading the gazetteer file
    mocker.patch('builtins.open', mock_open(read_data=gazetteer_content))
    
    # Instantiate the tagger - this will now use the mocked open
    tagger_instance = TalmudTagger()
    # Verify the mock worked (optional check)
    assert len(tagger_instance.name_gazetteer) == 4
    assert "Rabbi Akiva" in tagger_instance.name_gazetteer
    
    return tagger_instance

def test_generate_tags_from_entities(tagger):
    """Test tag generation based on entities."""
    processed_en = {
        'entities': [
            ("Rabbi Akiva", "PERSON"), # In mock gazetteer
            ("Babylonia", "GPE"),
            ("a book", "WORK_OF_ART") # Should be ignored
        ],
        'noun_phrases': [],
        'sentences': [],
        'doc': MockProcessedDoc("Text mentioning Rabbi Akiva and Babylonia.") # Add mock doc
    }
    topics = []
    tags = tagger.generate_tags(processed_en, topics)
    # NER finds Rabbi Akiva, Gazetteer also finds Rabbi Akiva. Set handles deduplication.
    assert set(tags) == {"person:rabbi akiva", "place:babylonia"}
    assert len(tags) == 2

def test_generate_tags_from_noun_phrases(tagger):
    """Test tag generation based on keywords in noun phrases."""
    processed_en = {
        'entities': [],
        'noun_phrases': [
            "the morning prayer",
            "a discussion about blessings",
            "some other phrase"
        ],
        'sentences': [],
        'doc': MockProcessedDoc("Text about prayer and blessings.") # Add mock doc
    }
    topics = []
    tags = tagger.generate_tags(processed_en, topics)
    assert set(tags) == {"topic:prayer", "topic:blessings"}
    assert len(tags) == 2

def test_generate_tags_from_gazetteer(tagger):
    """Test tag generation specifically from gazetteer matches."""
    processed_en = {
        'entities': [("Some Other Person", "PERSON")], # NER finds someone else
        'noun_phrases': [],
        'sentences': [],
        'doc': MockProcessedDoc("This text mentions Rav Ashi. It also mentions zutra bar toviyya (lowercase). But not Rabbi Meir.") # Add mock doc with gazetteer names
    }
    topics = []
    tags = tagger.generate_tags(processed_en, topics)
    # Expected: NER tag + gazetteer matches (case-insensitive)
    # Note: Gazetteer names are lowercased and cleaned in the tag
    assert set(tags) == {
        "person:some other person", # From NER
        "person:rav ashi",          # From Gazetteer (exact case)
        "person:zutra bar toviyya"  # From Gazetteer (lowercase match)
    }
    assert len(tags) == 3

def test_generate_tags_deduplication(tagger):
    """Test that generated tags are deduplicated (NER + Gazetteer)."""
    processed_en = {
        'entities': [("Rabbi Akiva", "PERSON")], # NER finds Rabbi Akiva
        'noun_phrases': ["the prayer of Rabbi Akiva", "another prayer"], 
        'sentences': [],
        'doc': MockProcessedDoc("Text about the prayer of Rabbi Akiva.") # Gazetteer also finds Rabbi Akiva
    }
    topics = []
    tags = tagger.generate_tags(processed_en, topics)
    # NER finds Rabbi Akiva, Gazetteer finds Rabbi Akiva. Should only appear once.
    # Noun phrase rule finds prayer twice. Should only appear once.
    assert tags.count("person:rabbi akiva") == 1
    assert tags.count("topic:prayer") == 1
    assert set(tags) == {"person:rabbi akiva", "topic:prayer"}
    assert len(tags) == 2

def test_extract_topics(tagger):
    """Test topic extraction with mocked scikit-learn components."""
    texts = ["some text document one", "another text document two"]
    n_topics = 2
    topics = tagger.extract_topics(texts, n_topics=n_topics)

    # Assertions based on the mocked components_
    # MockLDA components_: [[0.1, 0.8, 0.1], [0.5, 0.1, 0.4]]
    # MockVectorizer features: ["word1", "word2", "word3"]
    # Topic 0 top word should be "word2" (weight 0.8)
    # Topic 1 top word should be "word1" (weight 0.5)

    assert len(topics) == n_topics
    # Check if the top word extraction logic works with the mock components
    # argsort()[:-10 - 1:-1] gets top 10 words in descending order
    # For our simple mock with 3 words, it will get all words sorted
    # Topic 0: argsort -> [0, 2, 1], reversed -> [1, 2, 0] -> ["word2", "word3", "word1"]
    # Topic 1: argsort -> [1, 2, 0], reversed -> [0, 2, 1] -> ["word1", "word3", "word2"]
    assert topics[0][0] == "word2" # Top word for topic 0
    assert topics[1][0] == "word1" # Top word for topic 1
    # Check number of words returned (should be up to 10, or fewer if fewer features)
    assert len(topics[0]) == 3 # Mock has 3 features
    assert len(topics[1]) == 3
