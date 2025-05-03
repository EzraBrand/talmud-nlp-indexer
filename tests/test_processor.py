# tests/test_processor.py
import pytest
from processor import TextProcessor
import numpy as np
import torch # Import torch for mocking tensor operations

# Mock spaCy model and doc object
class MockSpacyToken:
    def __init__(self, text):
        self.text = text

class MockSpacySpan:
    def __init__(self, text, label_):
        self.text = text
        self.label_ = label_

class MockSpacyDoc:
    def __init__(self, text):
        self.text = text
        self.ents = [MockSpacySpan("Example Person", "PERSON"), MockSpacySpan("Example Place", "GPE")]
        self.noun_chunks = [MockSpacyToken("example noun phrase")]
        self.sents = [MockSpacyToken("This is a sentence.")]

class MockSpacyNLP:
    def __call__(self, text):
        return MockSpacyDoc(text)

# Mock Transformers tokenizer and model
class MockTokenizerOutput:
    def __init__(self):
        # Dummy tensor structure, needs to be a torch tensor
        self.data = {'input_ids': torch.tensor([[101, 7592, 102]])}

    def __getitem__(self, item):
         # Allow dictionary-like access
        return self.data[item]

    def keys(self):
        return self.data.keys()

    def values(self):
        return self.data.values()

    def items(self):
        return self.data.items()


class MockModelOutput:
    def __init__(self):
        # Dummy embedding tensor (batch_size=1, sequence_length=3, hidden_size=10)
        # Using a small hidden_size for simplicity
        # Needs to be a torch tensor
        self.last_hidden_state = torch.rand(1, 3, 10)

class MockHFTokenizer:
    def __call__(self, text, return_tensors, truncation, max_length):
        # Basic tokenization simulation
        return MockTokenizerOutput()

class MockHFModel:
    # Make it behave like a callable model
    def __call__(self, **tokens):
        return MockModelOutput()

@pytest.fixture
def text_processor(mocker):
    """Fixture to create a TextProcessor with mocked models."""
    # Mock spacy.load
    mocker.patch('processor.spacy.load', return_value=MockSpacyNLP())
    # Mock AutoTokenizer.from_pretrained
    mocker.patch('processor.AutoTokenizer.from_pretrained', return_value=MockHFTokenizer())
    # Mock AutoModel.from_pretrained
    mocker.patch('processor.AutoModel.from_pretrained', return_value=MockHFModel())
    # Mock torch.no_grad context manager
    mock_no_grad = mocker.patch('processor.torch.no_grad')
    mock_no_grad.return_value.__enter__.return_value = None # Mock the context manager entry
    mock_no_grad.return_value.__exit__.return_value = None # Mock the context manager exit

    # Mock the .mean() call which happens on the tensor in process_hebrew
    # The tensor is outputs.last_hidden_state
    # We need to mock the mean method of the torch.Tensor class specifically for this instance
    mock_mean = mocker.patch('torch.Tensor.mean', return_value=torch.rand(1, 10)) # Return a tensor of shape (batch, hidden_size)
    # Store the mock_mean to potentially check calls later if needed
    # mocker.mock_mean = mock_mean # Optional: store if needed for assertions

    return TextProcessor()

def test_process_english(text_processor):
    """Test basic English processing."""
    result = text_processor.process_english("This is English text.")
    assert 'entities' in result
    assert 'noun_phrases' in result
    assert 'sentences' in result
    assert len(result['entities']) == 2 # Based on MockSpacyDoc
    assert result['entities'][0] == ("Example Person", "PERSON")
    assert len(result['noun_phrases']) == 1
    assert result['noun_phrases'][0] == "example noun phrase"
    assert len(result['sentences']) == 1
    assert result['sentences'][0] == "This is a sentence."

def test_process_hebrew(text_processor, mocker): # Add mocker here if needed for specific test mocking
    """Test basic Hebrew processing (mocked)."""
    # The .mean() mock is now in the fixture, so it applies here
    result = text_processor.process_hebrew("זה טקסט בעברית.")

    assert 'embeddings' in result
    assert 'tokens' in result
    # Check type and shape rather than exact value due to mocking
    assert isinstance(result['embeddings'], torch.Tensor) # Should be a torch tensor
    assert result['embeddings'].shape == (1, 10) # Matches the mocked mean result shape

    # Optional: Verify that the mocked mean was called if the mock was stored in the fixture
    # assert mocker.mock_mean.called

def test_clean_text(text_processor):
    """Test basic text cleaning (newlines, returns, stripping)."""
    text_en = " Text with\nnewlines and\rreturns. "
    text_he = " טקסט עם\nשורה חדשה ו\rחזרה. "
    
    # English: Should extract nothing as there are no <b> tags, then strip
    cleaned_en = text_processor.clean_text(text_en, 'en')
    assert cleaned_en == ""
    
    # Hebrew: Should remove HTML (none here) and replace newlines/returns
    cleaned_he = text_processor.clean_text(text_he, 'he')
    assert cleaned_he == "טקסט עם שורה חדשה ו חזרה."

def test_clean_text_html(text_processor):
    """Test HTML tag removal/extraction during cleaning."""
    text = "Plain text. <b>Bold part 1.</b> More plain. <b>Bold part 2 with <i>nested</i> tag.</b>\n<b>Another bold.</b>"
    
    # English: Extract only content within <b> tags, join, clean
    cleaned_en = text_processor.clean_text(text, 'en')
    # Expected: "Bold part 1. Bold part 2 with nested tag. Another bold."
    # Note: The inner <i> tag is removed in the second cleaning pass within the 'en' block
    expected_en = "Bold part 1. Bold part 2 with nested tag. Another bold."
    assert cleaned_en == expected_en
    
    # Hebrew: Remove all tags, replace newlines
    cleaned_he = text_processor.clean_text(text, 'he')
    expected_he = "Plain text. Bold part 1. More plain. Bold part 2 with nested tag. Another bold."
    assert cleaned_he == expected_he
