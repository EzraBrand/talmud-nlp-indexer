"""
Talmud NLP Indexer - A system for analyzing and tagging the Talmud Bavli.
"""
from .api import SefariaAPI
from .processor import TextProcessor
from .tagging import TalmudTagger

__version__ = '0.1.0'


class TalmudProcessor:
    """Main interface for the Talmud NLP Indexer."""
    
    def __init__(self):
        """Initialize the Talmud processor."""
        self.api = SefariaAPI()
        self.text_processor = TextProcessor()
        self.tagger = TalmudTagger()
    
    def process_daf(self, tractate: str, daf: str):
        """
        Process a single Talmud page.
        
        Args:
            tractate: Name of the tractate
            daf: Page reference
            
        Returns:
            Dictionary containing processed data and tags
        """
        # Fetch text from API
        page_data = self.api.fetch_talmud_page(tractate, daf)
        
        # Extract English and Hebrew text
        en_text = " ".join(page_data.get('text', []))
        he_text = " ".join(page_data.get('he', []))
        
        # Clean texts
        en_text_clean = self.text_processor.clean_text(en_text, 'en')
        he_text_clean = self.text_processor.clean_text(he_text, 'he')
        
        # Process texts
        en_processed = self.text_processor.process_english(en_text_clean)
        he_processed = self.text_processor.process_hebrew(he_text_clean)
        
        # Extract topics (simple approach for single page)
        topics = self.tagger.extract_topics([en_text_clean])
        
        # Generate tags
        tags = self.tagger.generate_tags(en_processed, topics)
        
        return {
            'page_ref': f"{tractate}.{daf}",
            'en_text': en_text,
            'he_text': he_text,
            'en_processed': en_processed,
            'he_processed': he_processed,
            'topics': topics,
            'tags': tags
        }