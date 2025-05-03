"""
Integration tests for the main script (main.py).
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open, call
import os
import json

# Import the components and the main function
from api import SefariaAPI
from processor import TextProcessor
from tagging import TalmudTagger
import main

# Define dummy data for mocking
DUMMY_PAGE_DATA = {
    'ref': 'Berakhot 2a',
    'text': ['English text for 2a.'],
    'he': ['Hebrew text for 2a.']
}
DUMMY_EN_PROCESSED = {'entities': [('Person A', 'PERSON')], 'noun_phrases': ['np1'], 'sentences': ['s1']}
# Mock a tensor-like object with a shape attribute for Hebrew embeddings
mock_embedding_tensor = MagicMock()
mock_embedding_tensor.shape = [1, 768]
DUMMY_HE_PROCESSED = {'embeddings': mock_embedding_tensor} # Match structure expected by main.py
DUMMY_TAGS = ['person:Person A', 'topic:np1']

@patch('main.SefariaAPI')
@patch('main.TextProcessor')
@patch('main.TalmudTagger')
@patch('os.makedirs')
@patch('builtins.open', new_callable=mock_open)
@patch('json.dump')
def test_main_pipeline(
    mock_json_dump: MagicMock,
    mock_file_open: MagicMock,
    mock_makedirs: MagicMock,
    mock_tagger_cls: MagicMock,
    mock_processor_cls: MagicMock,
    mock_api_cls: MagicMock,
    mocker # pytest-mock fixture
):
    """Test the main processing pipeline orchestration."""
    # --- Mock Instantiation and Method Returns ---

    # Mock API
    mock_api_instance = MagicMock(spec=SefariaAPI)
    mock_api_instance.fetch_talmud_page.return_value = DUMMY_PAGE_DATA
    mock_api_cls.return_value = mock_api_instance

    # Mock Processor
    mock_processor_instance = MagicMock(spec=TextProcessor)
    mock_processor_instance.clean_text.side_effect = lambda text, lang: f"cleaned_{lang}_{text[:5]}"
    mock_processor_instance.process_english.return_value = DUMMY_EN_PROCESSED
    mock_processor_instance.process_hebrew.return_value = DUMMY_HE_PROCESSED
    mock_processor_cls.return_value = mock_processor_instance

    # Mock Tagger
    mock_tagger_instance = MagicMock(spec=TalmudTagger)
    mock_tagger_instance.generate_tags.return_value = DUMMY_TAGS
    mock_tagger_cls.return_value = mock_tagger_instance

    # --- Run the main function ---
    main.main()

    # --- Assertions ---

    # Check component initialization
    mock_api_cls.assert_called_once()
    mock_processor_cls.assert_called_once()
    mock_tagger_cls.assert_called_once()

    # Check directory creation
    mock_makedirs.assert_called_once_with("data", exist_ok=True)

    # Check API calls (should be 10 pages: 2a-6b, 7a)
    assert mock_api_instance.fetch_talmud_page.call_count == 11 # 2a to 7a inclusive
    expected_api_calls = []
    for num in range(2, 8):
        for side in ['a', 'b']:
            if num == 7 and side == 'b': continue # Skip 7b
            daf = f"{num}{side}"
            expected_api_calls.append(call("Berakhot", daf))
    mock_api_instance.fetch_talmud_page.assert_has_calls(expected_api_calls)

    # Check processor calls (example for the first page '2a')
    mock_processor_instance.clean_text.assert_any_call('English text for 2a.', 'en')
    mock_processor_instance.clean_text.assert_any_call('Hebrew text for 2a.', 'he')
    mock_processor_instance.process_english.assert_any_call('cleaned_en_Engli')
    mock_processor_instance.process_hebrew.assert_any_call('cleaned_he_Hebre')
    assert mock_processor_instance.clean_text.call_count == 22 # 11 pages * 2 languages
    assert mock_processor_instance.process_english.call_count == 11
    assert mock_processor_instance.process_hebrew.call_count == 11


    # Check tagger calls (example for the first page '2a')
    # Note: topics=[] is hardcoded in main.py currently
    mock_tagger_instance.generate_tags.assert_any_call(DUMMY_EN_PROCESSED, [])
    assert mock_tagger_instance.generate_tags.call_count == 11

    # Check file writing
    assert mock_file_open.call_count == 11
    expected_file_calls = []
    expected_json_calls = []
    for num in range(2, 8):
        for side in ['a', 'b']:
            if num == 7 and side == 'b': continue # Skip 7b
            daf = f"{num}{side}"
            output_file = f"data/Berakhot_{daf}.json"
            expected_file_calls.append(call(output_file, 'w', encoding='utf-8'))

            # Construct expected serializable data for json.dump
            expected_serializable = {
                'ref': DUMMY_PAGE_DATA['ref'], # Using the mocked return ref
                'en_text': 'English text for 2a.',
                'he_text': 'Hebrew text for 2a.',
                'en_processed': {
                    'entities': DUMMY_EN_PROCESSED['entities'],
                    'noun_phrases': DUMMY_EN_PROCESSED['noun_phrases'],
                    'sentences': DUMMY_EN_PROCESSED['sentences']
                },
                'he_processed': {'embedding_shape': DUMMY_HE_PROCESSED['embeddings'].shape},
                'tags': DUMMY_TAGS
            }
            # json.dump is called with the file handle from mock_open
            expected_json_calls.append(call(expected_serializable, mock_file_open.return_value, ensure_ascii=False, indent=2))

    # Filter out the __enter__ and __exit__ calls from the mock_open calls
    actual_file_calls = [c for c in mock_file_open.call_args_list if c[0]] # Only keep calls with args
    assert actual_file_calls == expected_file_calls

    # Check json dump calls
    mock_json_dump.assert_has_calls(expected_json_calls)
    assert mock_json_dump.call_count == 11

