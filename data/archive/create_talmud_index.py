import csv
import re
from collections import Counter
from html import unescape

# Load concepts gazetteer
concepts = []
with open('talmud_concepts_gazetteer.txt', 'r', encoding='utf-8') as f:
    for line in f:
        concept = line.strip()
        if concept:  # Skip empty lines
            concepts.append(concept)

print(f"Loaded {len(concepts)} concepts from gazetteer")

# Create regex pattern for case-insensitive matching
# Escape special regex characters and sort by length (longest first) to match longer phrases first
concepts_sorted = sorted(concepts, key=len, reverse=True)
pattern = '|'.join(re.escape(concept) for concept in concepts_sorted)
concept_regex = re.compile(pattern, re.IGNORECASE)

# Process Talmud CSV
page_keywords = {}  # Dictionary to store keywords by page
# Try different encodings
encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
for encoding in encodings:
    try:
        with open('steinsaltz_talmud_combined_richHTML.csv', 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            # Test read first row
            next(reader)
        print(f"Successfully opened file with {encoding} encoding")
        break
    except (UnicodeDecodeError, StopIteration):
        continue

with open('steinsaltz_talmud_combined_richHTML.csv', 'r', encoding=encoding) as f:
    reader = csv.DictReader(f)

    for row_num, row in enumerate(reader, start=1):
        if row_num > 1000:  # Limit to first 1000 rows
            break

        location = row['Column1']
        text = row['Column2']

        # Extract page number (e.g., "Berakhot 2a:1" -> "Berakhot 2a")
        if ':' in location:
            page = location.rsplit(':', 1)[0]
        else:
            page = location

        # Remove HTML tags and unescape HTML entities
        text_clean = re.sub(r'<[^>]+>', '', text)
        text_clean = unescape(text_clean)

        # Find all concept matches (case-insensitive)
        matches = concept_regex.findall(text_clean)

        if matches:
            # Initialize page in dictionary if not exists
            if page not in page_keywords:
                page_keywords[page] = Counter()

            # Add matches to this page's counter
            for match in matches:
                page_keywords[page][match.lower()] += 1

            print(f"Row {row_num}: {location} (page: {page}) - Found {len(matches)} keyword instances")
        else:
            print(f"Row {row_num}: {location} (page: {page}) - No keywords found")

# Custom sort function for Talmud pages
def sort_talmud_page(page):
    """Sort Talmud pages correctly (e.g., 2a before 2b before 3a)"""
    import re
    match = re.match(r'(.+?)\s+(\d+)([ab])', page)
    if match:
        tractate, page_num, side = match.groups()
        return (tractate, int(page_num), side)
    return (page, 0, 'a')

# Convert to results list sorted correctly
results = []
for page in sorted(page_keywords.keys(), key=sort_talmud_page):
    keyword_counts = page_keywords[page]

    # Sort by count (descending)
    sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)

    # Create comma-separated list of keywords (without counts)
    keywords_str = ', '.join(keyword for keyword, count in sorted_keywords)

    # Create Sefaria link (format: https://www.sefaria.org.il/Tractate.PageSide)
    # e.g., "Berakhot 2a" -> "https://www.sefaria.org.il/Berakhot.2a"
    sefaria_link = f"https://www.sefaria.org.il/{page.replace(' ', '.')}"

    results.append({
        'location': page,
        'keywords': keywords_str,
        'sefaria_link': sefaria_link
    })

    print(f"\nPage {page}: {len(keyword_counts)} unique keywords, {sum(keyword_counts.values())} total occurrences")

# Write results to CSV
output_file = 'talmud_index_final.csv'
try:
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['location', 'keywords', 'sefaria_link'])
        writer.writeheader()
        writer.writerows(results)
    print(f"Output written to: {output_file}")
except PermissionError:
    print(f"Warning: Could not write to {output_file} - file may be open. Close it and try again.")

print(f"\nCompleted! Created index with {len(results)} entries")
print(f"Output written to: {output_file}")
