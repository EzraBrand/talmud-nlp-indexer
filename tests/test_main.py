"""
Integration tests for the main script (main.py).
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open, call, PropertyMock
import os
import json
import tempfile
import spacy

# Import the components and the main function
from api import SefariaAPI
from processor import TextProcessor
from tagging import TalmudTagger
import main

# Define dummy data for mocking
DUMMY_PAGE_DATA = {
    'ref': 'Berakhot 2a',
    'text': ['<b>English text for 2a.</b>'],
    'he': ['Hebrew text for 2a.']
}
mock_nlp = spacy.blank("en")
mock_doc_instance = mock_nlp("cleaned_en_Engli")
DUMMY_EN_PROCESSED = {
    'entities': [('Person A', 'PERSON')],
    'noun_phrases': ['np1'],
    'sentences': ['s1'],
    'italicized_words': ['italic_word'],
    'doc': mock_doc_instance
}
mock_embedding_tensor = MagicMock()
mock_embedding_tensor.shape = [1, 768]
DUMMY_HE_PROCESSED = {'embeddings': mock_embedding_tensor}
DUMMY_TAGS = ['person:Person A', 'topic:np1']

@patch('main.SefariaAPI')
@patch('main.TextProcessor')
@patch('main.TalmudTagger')
@patch('os.makedirs')
@patch('builtins.open', new_callable=mock_open)
@patch('json.dump')
@patch('main.generate_markdown')
def test_main_pipeline(
    mock_generate_markdown: MagicMock,
    mock_json_dump: MagicMock,
    mock_file_open: MagicMock,
    mock_makedirs: MagicMock,
    mock_tagger_cls: MagicMock,
    mock_processor_cls: MagicMock,
    mock_api_cls: MagicMock,
    mocker
):
    """Test the main processing pipeline orchestration."""
    # --- Mock Instantiation and Method Returns ---

    # Mock API
    mock_api_instance = MagicMock(spec=SefariaAPI)
    mock_api_instance.fetch_talmud_page.return_value = DUMMY_PAGE_DATA
    mock_api_cls.return_value = mock_api_instance

    # Mock Processor
    mock_processor_instance = MagicMock(spec=TextProcessor)
    mock_processor_instance.clean_text.return_value = ("cleaned_he_Hebre", [])
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

    # Check API calls
    assert mock_api_instance.fetch_talmud_page.call_count == 11
    expected_api_calls = []
    for num in range(2, 8):
        for side in ['a', 'b']:
            if num == 7 and side == 'b': continue
            daf = f"{num}{side}"
            expected_api_calls.append(call("Berakhot", daf))
    mock_api_instance.fetch_talmud_page.assert_has_calls(expected_api_calls)

    # Check processor calls
    assert mock_processor_instance.clean_text.call_count == 11
    mock_processor_instance.clean_text.assert_any_call('Hebrew text for 2a.', 'he')
    mock_processor_instance.process_english.assert_any_call('<b>English text for 2a.</b>')
    mock_processor_instance.process_hebrew.assert_any_call('cleaned_he_Hebre')
    assert mock_processor_instance.process_english.call_count == 11
    assert mock_processor_instance.process_hebrew.call_count == 11

    # Check tagger calls
    mock_tagger_instance.generate_tags.assert_any_call(DUMMY_EN_PROCESSED, [])
    assert mock_tagger_instance.generate_tags.call_count == 11

    # Check file writing (JSON)
    assert mock_json_dump.call_count == 11
    expected_serializable = {
        'ref': DUMMY_PAGE_DATA['ref'],
        'en_text': '<b>English text for 2a.</b>',
        'he_text': 'Hebrew text for 2a.',
        'en_processed': {
            'entities': DUMMY_EN_PROCESSED['entities'],
            'noun_phrases': DUMMY_EN_PROCESSED['noun_phrases'],
            'sentences': DUMMY_EN_PROCESSED['sentences'],
            'italicized_words': DUMMY_EN_PROCESSED['italicized_words']
        },
        'he_processed': {'embedding_shape': list(DUMMY_HE_PROCESSED['embeddings'].shape)},
        'tags': DUMMY_TAGS
    }
    mock_json_dump.assert_has_calls([call(expected_serializable, mock_file_open.return_value, ensure_ascii=False, indent=2)], any_order=True)

    # Check generate_markdown call
    assert mock_generate_markdown.call_count == 11
    expected_result_arg = {
        'ref': DUMMY_PAGE_DATA['ref'],
        'en_text': '<b>English text for 2a.</b>',
        'he_text': 'Hebrew text for 2a.',
        'en_processed': DUMMY_EN_PROCESSED,
        'he_processed': DUMMY_HE_PROCESSED,
        'tags': DUMMY_TAGS
    }
    mock_generate_markdown.assert_any_call(expected_result_arg, 'data/Berakhot_2a.md')

# Load a blank spaCy model for mocking Doc and Span
nlp = spacy.blank("en")

def test_generate_markdown_override():
    """Test generate_markdown prioritization and exclusion of specific spaCy labels."""
    mock_text = "Recite Shema. The Master said Rabbi Eliezer mentioned midnight at ACME Corp."
    
    # --- Create Mocks for Doc, Sents, Ents ---
    mock_doc = MagicMock() 
    mock_doc.text = mock_text

    mock_sent = MagicMock(spec=spacy.tokens.Span)
    mock_sent.start_char = 0
    mock_sent.end_char = len(mock_text)
    mock_sent.text = mock_text
    mock_doc.sents = [mock_sent] 

    mock_ents = []
    entities_data = [
        (7, 12, "Shema", "PERSON"),          
        (14, 24, "The Master", "WORK_OF_ART"), # spaCy=WORK_OF_ART, Gazetteer=person -> Should appear as person
        (30, 43, "Rabbi Eliezer", "PERSON"), 
        (54, 62, "midnight", "TIME"),         # No gazetteer -> Should appear as TIME
        (66, 76, "ACME Corp.", "ORG")         # spaCy=ORG, No gazetteer -> Should be excluded
    ]
    for start, end, text, label in entities_data:
        ent = MagicMock(spec=spacy.tokens.Span)
        ent.start_char = start
        ent.end_char = end
        ent.text = text
        ent.label_ = label
        ent.sent = mock_sent 
        mock_ents.append(ent)
    mock_doc.ents = mock_ents 

    # --- Prepare Result Dictionary ---
    result = {
        'ref': 'Test.1a',
        'tags': [
            'concept:shema', 
            'person:shema', 
            'person:master', # This overrides WORK_OF_ART for "The Master"
            'person:rabbi_eliezer',
            'topic:prayer'
            # No gazetteer tag for ACME Corp.
        ],
        'en_processed': {
            'doc': mock_doc, 
            'italicized_words': ['test_italic']
        }
    }
    
    # --- Run and Assert ---
    temp_dir = tempfile.mkdtemp()
    output_md_path = os.path.join(temp_dir, "test_output.md")
        
    try:
        main.generate_markdown(result, output_md_path) 
        
        with open(output_md_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Assertions
        assert "# Test.1a" in content
        assert "- concept:shema" in content
        assert "- person:master" in content
        assert "- test_italic" in content
        
        # Check annotations
        assert "**Shema**`[concept]`" in content # Overridden by gazetteer
        assert "**The Master**`[person]`" in content # Overridden by gazetteer (person:master)
        assert "**Rabbi Eliezer**`[person]`" in content # Matches gazetteer
        assert "**midnight**`[TIME]`" in content # Falls back to spaCy (TIME is not excluded)
        
        # Assert EXCLUSION
        assert "**ACME Corp.**`[ORG]`" not in content # Should be excluded

    finally:
        if os.path.exists(output_md_path):
            os.remove(output_md_path)
        os.rmdir(temp_dir)

