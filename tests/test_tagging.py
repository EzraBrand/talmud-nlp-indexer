# tests/test_tagging.py
import pytest
from tagging import TalmudTagger
import numpy as np # Needed for mock LDA components
from unittest.mock import mock_open, MagicMock, call # Import mock_open, MagicMock, and call

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
    """Fixture to create a TalmudTagger instance with mocked sklearn and gazetteers."""
    # Mock scikit-learn components
    mocker.patch('tagging.CountVectorizer', return_value=MockVectorizer())
    mocker.patch('tagging.LatentDirichletAllocation', side_effect=lambda n_components, random_state: MockLDA(n_components, random_state))

    # Mock gazetteer file reading for all four files
    name_gazetteer_content = "Rabbi Akiva\nRav Ashi\nShimon ben Lakish\nZutra bar Toviyya\nDavid" # Add David to test overlap
    toponym_gazetteer_content = "Babylonia\nJerusalem\nAkko\nPumbedita"
    concept_gazetteer_content = "Shekhina\nbat kol\ntefillin\nGehenna\nShabbat"
    bible_name_gazetteer_content = "Moses\nAaron\nDavid\nSarah" # Add David here too

    # Mock os.path.exists to always return True for simplicity in this fixture
    mocker.patch('tagging.os.path.exists', return_value=True)

    # Mock builtins.open to handle different files
    mock_file_map = {
        "data/talmud_names_gazetteer.txt": mock_open(read_data=name_gazetteer_content).return_value,
        "data/talmud_toponyms_gazetteer.txt": mock_open(read_data=toponym_gazetteer_content).return_value,
        "data/talmud_concepts_gazetteer.txt": mock_open(read_data=concept_gazetteer_content).return_value,
        "data/bible_names_gazetteer.txt": mock_open(read_data=bible_name_gazetteer_content).return_value, # Add bible names mock
    }
    # Use a side_effect function to return the correct mock file handle based on the path
    def open_side_effect(path, *args, **kwargs):
        if path in mock_file_map:
            # Return the file handle itself
            return mock_file_map[path]
        # Fallback for any other file path if needed, though not expected in this test
        return mock_open().return_value

    mocker.patch('builtins.open', side_effect=open_side_effect)

    # Instantiate the tagger - this will now use the mocked open
    tagger_instance = TalmudTagger()

    # Verify the mocks worked (optional check)
    assert len(tagger_instance.name_gazetteer) == 5 # Updated count
    assert "Rabbi Akiva" in tagger_instance.name_gazetteer
    assert "David" in tagger_instance.name_gazetteer
    assert len(tagger_instance.toponym_gazetteer) == 4
    assert "Jerusalem" in tagger_instance.toponym_gazetteer
    assert len(tagger_instance.concept_gazetteer) == 5
    assert "Shekhina" in tagger_instance.concept_gazetteer
    assert len(tagger_instance.bible_name_gazetteer) == 4 # Check bible gazetteer
    assert "Moses" in tagger_instance.bible_name_gazetteer
    assert "David" in tagger_instance.bible_name_gazetteer

    return tagger_instance

def test_generate_tags_from_entities(tagger):
    """Test tag generation based on entities (NER + Gazetteer)."""
    processed_en = {
        'entities': [
            ("Rabbi Akiva", "PERSON"), # In name gazetteer
            ("Babylonia", "GPE"),      # In toponym gazetteer
            ("Moses", "PERSON"),       # In bible name gazetteer
            ("a book", "WORK_OF_ART") # Should be ignored
        ],
        'noun_phrases': [],
        'sentences': [],
        'doc': MockProcessedDoc("Text mentioning Rabbi Akiva, Babylonia, and Moses.") # Add mock doc
    }
    topics = []
    tags = tagger.generate_tags(processed_en, topics)
    # NER finds Rabbi Akiva (PERSON) -> person:rabbi akiva
    # NER finds Babylonia (GPE) -> place:babylonia
    # NER finds Moses (PERSON), which is in bible gazetteer -> person:bible:moses
    assert set(tags) == {"person:rabbi akiva", "place:babylonia", "person:bible:moses"}
    assert len(tags) == 3

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

def test_generate_tags_from_name_gazetteer(tagger):
    """Test tag generation specifically from name gazetteer matches, handling bible name overlap."""
    processed_en = {
        'entities': [("Some Other Person", "PERSON")], # NER finds someone else
        'noun_phrases': [],
        'sentences': [],
        # David is in both name and bible gazetteers in the mock setup
        'doc': MockProcessedDoc("This text mentions Rav Ashi and David. It also mentions zutra bar toviyya (lowercase). But not Rabbi Meir.")
    }
    topics = []
    tags = tagger.generate_tags(processed_en, topics)
    # Expected:
    # - person:some other person (from NER)
    # - person:rav ashi (from Name Gazetteer)
    # - person:zutra bar toviyya (from Name Gazetteer, case-insensitive)
    # - person:bible:david (from Bible Gazetteer, takes precedence over Name Gazetteer match)
    assert set(tags) == {
        "person:some other person",
        "person:rav ashi",
        "person:zutra bar toviyya",
        "person:bible:david"
    }
    assert len(tags) == 4

def test_generate_tags_from_toponym_gazetteer(tagger):
    """Test tag generation specifically from toponym gazetteer matches."""
    processed_en = {
        'entities': [("Some Other Place", "GPE")], # NER finds somewhere else
        'noun_phrases': [],
        'sentences': [],
        'doc': MockProcessedDoc("Travel from Jerusalem to Akko, maybe via Pumbedita. Not Caesarea.") # Add mock doc with gazetteer toponyms
    }
    topics = []
    tags = tagger.generate_tags(processed_en, topics)
    # Expected: NER tag + gazetteer matches (case-insensitive)
    assert set(tags) == {
        "place:some other place", # From NER
        "place:jerusalem",        # From Gazetteer
        "place:akko",             # From Gazetteer
        "place:pumbedita"         # From Gazetteer
    }
    assert len(tags) == 4

def test_generate_tags_from_concept_gazetteer(tagger):
    """Test tag generation specifically from concept gazetteer matches."""
    processed_en = {
        'entities': [],
        'noun_phrases': [],
        'sentences': [],
        'doc': MockProcessedDoc("Discussion about the Shekhina and putting on tefillin before Shabbat. Also mentions bat kol.") # Add mock doc with gazetteer concepts
    }
    topics = []
    tags = tagger.generate_tags(processed_en, topics)
    # Expected: gazetteer matches (case-insensitive)
    assert set(tags) == {
        "concept:shekhina",
        "concept:tefillin",
        "concept:shabbat",
        "concept:bat kol"
    }
    assert len(tags) == 4

def test_generate_tags_from_bible_name_gazetteer(tagger):
    """Test tag generation specifically from bible name gazetteer matches."""
    processed_en = {
        'entities': [],
        'noun_phrases': [],
        'sentences': [],
        'doc': MockProcessedDoc("This text mentions Moses and Aaron. Also Sarah (lowercase). Not Abraham.")
    }
    topics = []
    tags = tagger.generate_tags(processed_en, topics)
    # Expected: Bible gazetteer matches (case-insensitive)
    assert set(tags) == {
        "person:bible:moses",
        "person:bible:aaron",
        "person:bible:sarah"
    }
    assert len(tags) == 3

def test_generate_tags_deduplication(tagger):
    """Test that generated tags are deduplicated (NER + Gazetteers + Keywords + Bible Names)."""
    processed_en = {
        'entities': [
            ("Rabbi Akiva", "PERSON"), # NER + Name Gazetteer
            ("Babylonia", "GPE"),       # NER + Toponym Gazetteer
            ("David", "PERSON")        # NER + Bible Gazetteer (also in Name Gazetteer mock)
        ],
        'noun_phrases': ["the prayer of Rabbi Akiva", "another prayer about Shabbat", "King David's prayer"], # Keywords: prayer, Shabbat; Names: Rabbi Akiva, David
        'sentences': [],
        'doc': MockProcessedDoc("Text about the prayer of Rabbi Akiva in Babylonia concerning Shabbat, mentioning David.") # Gazetteers find Akiva, Babylonia, Shabbat, David (Bible)
    }
    topics = []
    tags = tagger.generate_tags(processed_en, topics)
    # NER finds Rabbi Akiva -> person:rabbi akiva (1)
    # NER finds Babylonia -> place:babylonia (1)
    # NER finds David (Bible) -> person:bible:david (1)
    # Noun phrase rule finds prayer twice -> topic:prayer (1)
    # Noun phrase rule finds Shabbat, Concept Gazetteer finds Shabbat -> concept:shabbat (1)
    # Gazetteer finds Rabbi Akiva -> already tagged
    # Gazetteer finds Babylonia -> already tagged
    # Gazetteer finds Shabbat -> already tagged
    # Gazetteer finds David (Bible) -> already tagged
    assert tags.count("person:rabbi akiva") == 1
    assert tags.count("place:babylonia") == 1
    assert tags.count("person:bible:david") == 1
    assert tags.count("topic:prayer") == 1
    assert tags.count("concept:shabbat") == 1
    assert set(tags) == {"person:rabbi akiva", "place:babylonia", "person:bible:david", "topic:prayer", "concept:shabbat"}
    assert len(tags) == 5

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

def test_generate_tags_with_topics(tagger):
    """Test tag generation including topic tags from extract_topics."""
    processed_en = {
        'entities': [("Rabbi Akiva", "PERSON")],
        'noun_phrases': ["the morning prayer"],
        'sentences': [],
        'doc': MockProcessedDoc("Text about Rabbi Akiva and prayer.")
    }
    # Simulate topics returned by extract_topics (using the mock structure)
    # Mock returns [["word2", "word3", "word1"], ["word1", "word3", "word2"]]
    mock_topics = [["word2", "word3", "word1"], ["word1", "word3", "word2"]]

    tags = tagger.generate_tags(processed_en, mock_topics)

    # Expected tags:
    # - person:rabbi akiva (from NER/Gazetteer)
    # - topic:prayer (from noun phrase keyword)
    # - topic:word2 (from mock_topics[0][0])
    # - topic:word1 (from mock_topics[1][0])
    assert set(tags) == {
        "person:rabbi akiva",
        "topic:prayer",
        "topic:word2",
        "topic:word1"
    }
    assert len(tags) == 4
