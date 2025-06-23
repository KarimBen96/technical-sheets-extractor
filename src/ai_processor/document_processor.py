import fitz  # PyMuPDF
import json
import os
import re

# Import components
from utils.config import Config

CATALOG_DIR = Config.CATALOG_DIR
OUTPUT_DIR = Config.OUTPUT_DIR


def extract_header_text(blocks, page_height, header_zone_height=100):
    """Extract text that appears in the header zone of the page"""
    header_text = []
    
    for block in blocks:
        if block["type"] == 0:  # Text block
            y_pos = block["bbox"][1]  # Top y-coordinate
            if y_pos < header_zone_height:
                for line in block["lines"]:
                    for span in line["spans"]:
                        header_text.append(span["text"])
    
    return " ".join(header_text)


def extract_footer_text(blocks, page_height, footer_zone_height=100):
    """Extract text that appears in the footer zone of the page"""
    footer_text = []
    
    for block in blocks:
        if block["type"] == 0:  # Text block
            y_pos = block["bbox"][3]  # Bottom y-coordinate
            if y_pos > (page_height - footer_zone_height):
                for line in block["lines"]:
                    for span in line["spans"]:
                        footer_text.append(span["text"])
    
    return " ".join(footer_text)


def analyze_pdf_structure(pdf_path):
    """
    Analyze PDF structure using PyMuPDF and create metadata that can help Mistral AI
    with page identification and technical sheet detection.
    """
    # Open the PDF
    doc = fitz.open(pdf_path)

    # Document structure analysis
    document_analysis = {"total_pages": len(doc), "pages": []}

    # Process each page
    for page_num in range(len(doc)):
        page = doc[page_num]

        # Extract text with position info
        text_blocks = page.get_text("dict")["blocks"]

        # Get page dimensions
        page_width = page.rect.width
        page_height = page.rect.height

        # Find tables correctly - get the tables list instead of the TableFinder object
        table_finder = page.find_tables()
        tables = table_finder.tables if table_finder else []

        # Page metadata
        page_data = {
            "page_number": page_num + 1,
            "width": page_width,
            "height": page_height,
            "text_content": page.get_text(),
            "header_text": extract_header_text(text_blocks, page_height),
            "footer_text": extract_footer_text(text_blocks, page_height),
            "has_tables": len(tables) > 0,
            "image_count": len(page.get_images()),
            "likely_technical_sheet": is_likely_technical_sheet(
                page, text_blocks, tables
            ),
        }

        document_analysis["pages"].append(page_data)

    return document_analysis


# Update is_likely_technical_sheet to accept tables parameter
def is_likely_technical_sheet(page, text_blocks, tables=None):
    """Determine if a page is likely to be a technical sheet based on content patterns"""
    text = page.get_text().lower()

    # Check for common technical sheet indicators
    technical_indicators = [
        "technical data",
        "specifications",
        "tech spec",
        "technical sheet",
        "dimensions",
        "material properties",
        "electrical specifications",
        "installation requirements",
        "performance characteristics",
    ]

    # Check for tabular data which is common in technical sheets
    has_tables = tables is not None and len(tables) > 0

    # Check for measurement units which are common in technical sheets
    measurement_pattern = r"\b\d+(\.\d+)?\s*(mm|cm|m|in|ft|kg|g|lb|v|hz|w)\b"
    has_measurements = bool(re.search(measurement_pattern, text, re.IGNORECASE))

    # Count keyword matches
    keyword_matches = sum(1 for indicator in technical_indicators if indicator in text)

    # Determine if likely technical sheet based on multiple factors
    return (keyword_matches >= 2) or (has_tables and has_measurements)


def add_page_identifiers(pdf_path, output_path):
    """Add explicit page identifiers and save to a new PDF"""
    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_width = page.rect.width

        # Add explicit page marker at top-right
        marker_text = f"PAGE-ID: {page_num + 1}"
        page.insert_text(
            (page_width - 150, 20),  # Position at top-right
            marker_text,
            fontname="helv",
            fontsize=8,
            color=(0, 0, 0.8),  # Dark blue
            render_mode=0,
        )

        # Add machine-readable marker at bottom (could be replaced with QR code)
        page.insert_text(
            (20, page.rect.height - 10),
            f"<page:{page_num + 1}>",
            fontname="courier",
            fontsize=6,
            color=(0.7, 0.7, 0.7),  # Light gray
            render_mode=0,
        )

    doc.save(output_path)
    print(f"Added page identifiers and saved to {output_path}")
    return output_path


def main(catalog_pdf_path):
    # Step 1: Add explicit page identifiers
    enhanced_pdf_path = os.path.join(OUTPUT_DIR, f"enhanced_{os.path.basename(catalog_pdf_path)}")
    enhanced_pdf_path = add_page_identifiers(
        catalog_pdf_path, enhanced_pdf_path
    )

    # Step 2: Analyze PDF structure
    document_analysis = analyze_pdf_structure(enhanced_pdf_path)

    # Step 3: Save analysis as JSON (to feed to Mistral)
    analysis_path = f"{os.path.splitext(catalog_pdf_path)[0]}_analysis.json"
    with open(analysis_path, "w") as f:
        json.dump(document_analysis, f, indent=2)

    print(f"Document analysis saved to {analysis_path}")
    print(f"You can now feed both '{enhanced_pdf_path}' and the analysis to Mistral AI")

    # Optional: Return likely technical sheet pages to save time
    tech_sheet_pages = [
        page["page_number"]
        for page in document_analysis["pages"]
        if page["likely_technical_sheet"]
    ]
    print(f"Likely technical sheet pages: {tech_sheet_pages}")
    return enhanced_pdf_path, analysis_path, document_analysis, tech_sheet_pages


if __name__ == "__main__":
    catalog_pdf = "src/data/catalogs/Catalogue-Tertu-Equipements-1-10.pdf"  
    main(catalog_pdf)