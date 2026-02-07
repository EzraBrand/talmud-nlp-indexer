"""
Convert the Bible Names Concordance HTML to a PDF with page headers.
Each page header shows:
  - Top right: page number
  - Top center: "BRAND — <first entry name on this page>"

Two-pass approach:
  1. Playwright renders HTML -> base PDF (with top margin for headers)
  2. pdfplumber reads each page to find the first name entry
  3. reportlab stamps headers onto each page via pypdf merge
"""

import re
import sys
import io
import argparse
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright required. pip install playwright && python -m playwright install chromium")
    sys.exit(1)

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber required. pip install pdfplumber")
    sys.exit(1)

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("ERROR: pypdf required. pip install pypdf")
    sys.exit(1)

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    print("ERROR: reportlab required. pip install reportlab")
    sys.exit(1)


INPUT_PATH = "bible_names_concordance.html"
OUTPUT_PATH = "bible_names_concordance.pdf"

# Print CSS injected into the HTML for Chromium rendering
PRINT_CSS = """
<style>
@media print {
    nav.alpha-nav { display: none !important; }
    header { page-break-after: always; }
    .name-entry { page-break-before: always; page-break-inside: avoid; }
    .concordance-entry { page-break-inside: avoid; }
    .letter-heading { page-break-before: always; page-break-after: avoid; }
    .stats { page-break-before: always; }
    a.location { color: #1a0dab !important; }

    /* Denser text */
    body { font-size: 9pt !important; line-height: 1.35 !important; }
    .container { max-width: 100% !important; padding: 0 !important; }
    .concordance-entry .text-content { font-size: 8.5pt !important; line-height: 1.3 !important; }
    .concordance-entry { padding: 0.4rem 0.75rem !important; margin-bottom: 0.4rem !important; }
    .name-entry { margin-bottom: 1rem !important; }

    /* Remove colored backgrounds */
    body { background: white !important; }
    .concordance-entry { background: white !important; box-shadow: none !important; }
    header { background: white !important; color: #2c2417 !important; border-bottom-color: #999 !important; }
    mark { background: #e0e0e0 !important; }
}
</style>
"""


def inject_print_css(html_content):
    """Inject print CSS into the HTML."""
    if "</head>" in html_content:
        return html_content.replace("</head>", f"{PRINT_CSS}\n</head>")
    return PRINT_CSS + html_content


def render_base_pdf(html_path, temp_pdf_path):
    """Use Playwright/Chromium to render HTML to PDF with margin for headers."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file:///{html_path.resolve().as_posix()}")
        page.wait_for_load_state("networkidle")

        page.pdf(
            path=str(temp_pdf_path),
            format="A4",
            margin={
                "top": "2.2cm",      # extra space for stamped header
                "bottom": "1.5cm",
                "left": "1.8cm",
                "right": "1.8cm",
            },
            print_background=True,
        )
        browser.close()


def extract_entry_names_per_page(pdf_path, all_names):
    """
    For each page of the PDF, find the first bible name entry that appears.
    Uses a set of known names for matching.
    Returns: list of (page_index, entry_name_or_None)
    """
    # Build sorted list of names, longest first for greedy matching
    names_sorted = sorted(all_names, key=len, reverse=True)

    page_entries = []
    last_entry = None

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            found = None
            # Find the first name that appears on this page
            # Search by position: find earliest occurrence
            earliest_pos = len(text) + 1
            for name in names_sorted:
                pos = text.find(name)
                if pos != -1 and pos < earliest_pos:
                    earliest_pos = pos
                    found = name

            if found:
                last_entry = found
            page_entries.append(last_entry)

    return page_entries


def extract_names_from_html(html_content):
    """Extract all name entry headings from the concordance HTML."""
    # Match the name from: <h3>NAME<span class="match-count">...
    names = re.findall(r'<h3>([^<]+)<span class="match-count">', html_content)
    # Unescape HTML entities
    import html
    return [html.unescape(n) for n in names]


def create_header_overlay(page_entries, page_width, page_height, total_pages):
    """
    Create a PDF with only the header text on each page.
    Returns bytes of the overlay PDF.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    for i in range(total_pages):
        entry = page_entries[i] if i < len(page_entries) else None

        # Skip header on first page (title page)
        if i == 0:
            c.showPage()
            continue

        # --- Page number: top right ---
        c.setFont("Courier-Bold", 12)
        c.setFillColorRGB(0.25, 0.25, 0.25)
        page_num_text = str(i + 1)
        c.drawRightString(page_width - 1.8 * cm, page_height - 1.2 * cm, page_num_text)

        # --- Center header: BRAND - Bible Names Concordance — entry name ---
        if entry:
            header_text = f"BRAND - Bible Names Concordance \u2014 {entry}"
        else:
            header_text = "BRAND - Bible Names Concordance"

        c.setFont("Times-Bold", 10)
        c.setFillColorRGB(0.3, 0.3, 0.3)  # strong gray
        center_x = page_width / 2
        c.drawCentredString(center_x, page_height - 1.2 * cm, header_text)

        # --- Decorative line under header ---
        c.setStrokeColorRGB(0.6, 0.6, 0.6)  # gray line
        c.setLineWidth(0.5)
        c.line(1.8 * cm, page_height - 1.5 * cm,
               page_width - 1.8 * cm, page_height - 1.5 * cm)

        c.showPage()

    c.save()
    buf.seek(0)
    return buf


def stamp_headers(base_pdf_path, overlay_buf, output_path):
    """Merge the header overlay onto each page of the base PDF."""
    base_reader = PdfReader(str(base_pdf_path))
    overlay_reader = PdfReader(overlay_buf)
    writer = PdfWriter()

    for i, page in enumerate(base_reader.pages):
        if i < len(overlay_reader.pages):
            overlay_page = overlay_reader.pages[i]
            page.merge_page(overlay_page)
        writer.add_page(page)

    with open(str(output_path), "wb") as f:
        writer.write(f)


def main():
    parser = argparse.ArgumentParser(description="Convert concordance HTML to PDF")
    parser.add_argument("-i", "--input", default=INPUT_PATH, help="Input HTML file")
    parser.add_argument("-o", "--output", default=OUTPUT_PATH, help="Output PDF file")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    temp_pdf = input_path.with_name("_temp_base.pdf")

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    # Inject print CSS into a temp HTML
    print(f"Reading {input_path}...")
    html_content = input_path.read_text(encoding="utf-8")
    styled_html = inject_print_css(html_content)
    temp_html = input_path.with_name("_temp_print.html")
    temp_html.write_text(styled_html, encoding="utf-8")

    # Pass 1: render to base PDF
    print("Pass 1: Rendering HTML to PDF with Playwright...")
    render_base_pdf(temp_html, temp_pdf)
    print(f"  Base PDF generated: {temp_pdf}")

    # Extract entry names from source HTML
    all_names = extract_names_from_html(html_content)
    print(f"  Found {len(all_names)} name entries in HTML.")

    # Pass 2: detect which entry is on which page
    print("Pass 2: Extracting entry names per page...")
    page_entries = extract_entry_names_per_page(temp_pdf, all_names)
    total_pages = len(page_entries)
    print(f"  Total pages: {total_pages}")

    # Get page dimensions from the base PDF
    base_reader = PdfReader(str(temp_pdf))
    first_page = base_reader.pages[0]
    page_width = float(first_page.mediabox.width)
    page_height = float(first_page.mediabox.height)
    print(f"  Page size: {page_width:.0f} x {page_height:.0f} points")

    # Create overlay with headers
    print("Creating header overlays...")
    overlay_buf = create_header_overlay(page_entries, page_width, page_height, total_pages)

    # Stamp headers onto base PDF
    print("Stamping headers onto PDF...")
    stamp_headers(temp_pdf, overlay_buf, output_path)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nWritten to {output_path} ({size_mb:.1f} MB)")

    # Cleanup temp files
    import gc
    gc.collect()
    try:
        temp_pdf.unlink(missing_ok=True)
    except PermissionError:
        print(f"  Note: could not delete {temp_pdf} (file in use). Delete manually.")
    temp_html.unlink(missing_ok=True)
    print("Cleaned up temp files.")


if __name__ == "__main__":
    main()
