#!/usr/bin/env python3
"""
Demo script to generate section-aware markdown output.
"""
import json
import os
import re
from api import SefariaAPI
from processor import TextProcessor
from tagging import TalmudTagger

def strip_nikud(text):
    """Strip Hebrew nikud (vowel points)"""
    nikud_pattern = r'[\u0591-\u05C7]'
    return re.sub(nikud_pattern, '', text)

def process_hebrew_section(he_text_raw):
    """Process Hebrew text for a section"""
    if not he_text_raw:
        return "No Hebrew text available for this section."
    
    # Remove HTML tags
    he_text_cleaned = re.sub(r'<[^>]+>', '', he_text_raw)
    # Strip nikud
    he_text_cleaned = strip_nikud(he_text_cleaned)
    # Split into sentences
    he_sentences = re.split(r'[.!?׃։]', he_text_cleaned)
    he_sentences = [sent.strip() for sent in he_sentences if sent.strip()]
    
    result = []
    for sentence in he_sentences:
        if sentence:
            result.append(f'<div dir="rtl">{sentence}</div>')
    
    return '\n\n'.join(result) if result else "No Hebrew text available for this section."

def generate_section_markdown(tractate, daf):
    """Generate section-aware markdown for a Talmud page"""
    
    # Initialize components
    sefaria_api = SefariaAPI()
    text_processor = TextProcessor()
    tagger = TalmudTagger()
    
    print(f"Processing {tractate}.{daf} with section-aware approach...")
    
    # Fetch sections
    sections_data = sefaria_api.fetch_talmud_page_sections(tractate, daf)
    print(f"Found {len(sections_data)} sections")
    
    # Generate markdown
    page_ref = f"{tractate} {daf}"
    markdown_content = [f"# {page_ref} (Section-Aware Analysis)\n"]
    
    # Process each section
    for i, section in enumerate(sections_data):
        section_num = section['section_number']
        print(f"  Processing section {section_num}/{len(sections_data)}...")
        
        markdown_content.append(f"## Section {section_num}")
        markdown_content.append("")
        
        # Hebrew text first
        markdown_content.append(f"### Hebrew Text (Section {section_num})")
        markdown_content.append("")
        hebrew_output = process_hebrew_section(section['he_text'])
        markdown_content.append(hebrew_output)
        markdown_content.append("")
        
        # English text 
        markdown_content.append(f"### English Text (Section {section_num})")
        markdown_content.append("")
        en_text = section['en_text']
        if en_text:
            # Simple processing - remove bold tags for cleaner display
            clean_en_text = re.sub(r'</?b>', '', en_text)
            clean_en_text = re.sub(r'</?i>', '*', clean_en_text)
            markdown_content.append(clean_en_text)
        else:
            markdown_content.append("No English text available for this section.")
        markdown_content.append("")
        
        # Section separator
        markdown_content.append("---")
        markdown_content.append("")
    
    # Write to file
    output_file = f"data/{tractate}_{daf}_sections_demo.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(markdown_content))
    
    print(f"Section-aware markdown saved to: {output_file}")
    return output_file

if __name__ == "__main__":
    # Generate section-aware output for Sanhedrin 91a
    output_file = generate_section_markdown("Sanhedrin", "91a")
    print(f"\nCompleted! Check {output_file}")
