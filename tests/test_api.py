# tests/test_api.py
import pytest
from api import SefariaAPI

def test_fetch_text_url_construction(mocker):
    """
    Test that fetch_text constructs the correct Sefaria API URL.
    """
    # Arrange
    api = SefariaAPI()
    test_ref = "Berakhot.2a"
    expected_url = f"{api.api_base}texts/{test_ref}"

    # Mock requests.get to prevent actual network call and capture the URL
    mock_get = mocker.patch('api.requests.get')

    # Act
    try:
        api.fetch_text(test_ref)
    except Exception:
        # We expect an exception because the mocked response won't be valid JSON,
        # but we only care about the URL passed to requests.get
        pass

    # Assert
    mock_get.assert_called_once_with(expected_url)

def test_fetch_talmud_page_calls_fetch_text(mocker):
    """
    Test that fetch_talmud_page correctly calls fetch_text.
    """
    # Arrange
    api = SefariaAPI()
    tractate = "Berakhot"
    daf = "3b"
    expected_ref = f"{tractate}.{daf}"

    # Mock the internal fetch_text method
    mock_fetch_text = mocker.patch.object(api, 'fetch_text', return_value={"text": "mocked"})

    # Act
    api.fetch_talmud_page(tractate, daf)

    # Assert
    mock_fetch_text.assert_called_once_with(expected_ref)
