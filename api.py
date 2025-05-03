
"""
Sefaria API client for fetching Talmudic texts.
"""
import requests
import json
from typing import Dict, Any, List, Optional


class SefariaAPI:
    """Client for interacting with the Sefaria API."""
    
    def __init__(self):
        """Initialize the Sefaria API client."""
        self.api_base = "https://www.sefaria.org/api/"
    
    def fetch_text(self, ref: str) -> Dict[str, Any]:
        """
        Fetch text from Sefaria API.
        
        Args:
            ref: Reference string in Sefaria format (e.g., "Berakhot.2a")
            
        Returns:
            Dictionary containing the text data
        """
        url = f"{self.api_base}texts/{ref}"
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to fetch text: {response.status_code}")
    
    def fetch_talmud_page(self, tractate: str, daf: str) -> Dict[str, Any]:
        """
        Fetch a specific page (daf) from the Talmud.
        
        Args:
            tractate: Name of the tractate (e.g., "Berakhot")
            daf: Page reference (e.g., "2a", "2b")
            
        Returns:
            Dictionary containing the page data
        """
        ref = f"{tractate}.{daf}"
        return self.fetch_text(ref)

    def fetch_tractate_range(self, tractate: str, start_daf: str, end_daf: str) -> List[Dict[str, Any]]:
        """
        Fetch a range of pages from a tractate.
        
        Args:
            tractate: Name of the tractate
            start_daf: Starting page reference
            end_daf: Ending page reference
            
        Returns:
            List of dictionaries containing the page data
        """
        # Parse daf references to generate the sequence
        pages = []
        start_num = int(start_daf[:-1])
        end_num = int(end_daf[:-1])
        
        for num in range(start_num, end_num + 1):
            # Each daf has an 'a' and 'b' side
            for side in ['a', 'b']:
                # Skip if before start_daf
                if num == start_num and side == 'a' and start_daf.endswith('b'):
                    continue
                # Skip if after end_daf
                if num == end_num and side == 'b' and end_daf.endswith('a'):
                    continue
                
                daf = f"{num}{side}"
                try:
                    page_data = self.fetch_talmud_page(tractate, daf)
                    pages.append(page_data)
                except Exception as e:
                    print(f"Error fetching {tractate}.{daf}: {e}")
        
        return pages