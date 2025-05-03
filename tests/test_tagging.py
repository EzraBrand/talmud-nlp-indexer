# tests/test_tagging.py
import pytest
from tagging import TalmudTagger
import numpy as np # Needed for mock LDA components

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

@pytest.fixture
def tagger(mocker): # Add mocker to the fixture
    """Fixture to create a TalmudTagger instance with mocked sklearn."""
    # Mock CountVectorizer
    mocker.patch('tagging.CountVectorizer', return_value=MockVectorizer())
    # Mock LatentDirichletAllocation
    mocker.patch('tagging.LatentDirichletAllocation', side_effect=lambda n_components, random_state: MockLDA(n_components, random_state))
    return TalmudTagger()

def test_generate_tags_from_entities(tagger):
    """Test tag generation based on entities."""
    processed_text = {
        'entities': [
            ("Rabbi Akiva", "PERSON"),
            ("Babylonia", "GPE"),
            ("a book", "WORK_OF_ART") # Should be ignored by current logic
        ],
        'noun_phrases': [],
        'sentences': []
    }
    topics = [] # Not used in this specific test case for entity tags
    tags = tagger.generate_tags(processed_text, topics)
    # Use set for assertion to ignore order
    assert set(tags) == {"person:rabbi akiva", "place:babylonia"}
    assert len(tags) == 2 # Only PERSON and GPE tags should be generated

def test_generate_tags_from_noun_phrases(tagger):
    """Test tag generation based on keywords in noun phrases."""
    processed_text = {
        'entities': [],
        'noun_phrases': [
            "the morning prayer",
            "a discussion about blessings",
            "some other phrase"
        ],
        'sentences': []
    }
    topics = []
    tags = tagger.generate_tags(processed_text, topics)
    # Use set for assertion to ignore order
    assert set(tags) == {"topic:prayer", "topic:blessings"}
    assert len(tags) == 2 # Only prayer and blessings tags expected

def test_generate_tags_deduplication(tagger):
    """Test that generated tags are deduplicated."""
    processed_text = {
        'entities': [("Rabbi Akiva", "PERSON")],
        'noun_phrases': ["the prayer of Rabbi Akiva", "another prayer"], # Generates 'topic:prayer' twice
        'sentences': []
    }
    topics = []
    tags = tagger.generate_tags(processed_text, topics)
    # Even if rules could potentially add the same tag twice, the final list should be unique
    assert tags.count("person:rabbi akiva") == 1
    assert tags.count("topic:prayer") == 1
    # Use set for assertion to ignore order and duplicates
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
