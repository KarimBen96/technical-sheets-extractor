import modal
app = modal.App("ai-pdf-splitter")

import sys
import os
import json
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# Import components
from ai_processor.ocr_analyzer import OCRAnalyzer
from ai_processor.prompt_list import prompt_technical_sheets
from ai_processor.document_processor import main as document_processor_main

@app.cls()
class Pipeline:
    """
    Coordinates the pipeline for extracting technical sheets from catalogs.
    """

    def __init__(
        self,
        mistral_api_key: Optional[str] = None,
        llm_model: str = "mistral-small-latest",
        confidence_threshold: float = 0.6,
        debug: bool = True,
        output_dir: Optional[str] = None,
    ):
        """
        Initialize the technical sheet extractor pipeline.

        Args:
            mistral_api_key: Mistral API key (if None, uses environment variable)
            llm_model: Model name to use
            confidence_threshold: Threshold for accepting a boundary
            debug: Enable debug output
            output_dir: Directory for saving results (if None, uses current directory)
        """
        self.debug = debug
        self.confidence_threshold = confidence_threshold

        # Set up output directory
        self.output_dir = output_dir or "results"
        os.makedirs(self.output_dir, exist_ok=True)

        # Initialize OCR analyzer with your prompt
        self.ocr_analyzer = OCRAnalyzer(
            api_key=mistral_api_key,
            model=llm_model,
            prompt=prompt_technical_sheets,
            debug=debug,
        )

    def _parse_boundaries(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse boundaries from LLM response using your prompt_technical_sheets format.

        Args:
            response: Response string from LLM

        Returns:
            List of processed technical sheet dictionaries
        """
        try:
            # Try to find JSON array in response
            start_idx = response.find("[")
            end_idx = response.rfind("]")

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx : end_idx + 1]
                boundaries = json.loads(json_str)

                # Normalize and filter boundaries according to your format
                normalized = []
                for b in boundaries:
                    # Check if it's a valid boundary
                    if not isinstance(b, dict):
                        continue

                    # Get confidence
                    confidence = 0.7
                    if "confidence" in b:
                        try:
                            confidence = float(b["confidence"])
                        except (ValueError, TypeError):
                            confidence = 0.7

                    # Only include boundaries above threshold
                    if confidence >= self.confidence_threshold:
                        # Process pages list
                        pages = []
                        if "pages" in b:
                            # Handle different formats - string or list
                            if isinstance(b["pages"], list):
                                pages = b["pages"]
                            elif isinstance(b["pages"], str):
                                # Try to parse as JSON list if it's a string
                                try:
                                    pages = json.loads(b["pages"])
                                except json.JSONDecodeError:
                                    # Try to parse comma-separated values
                                    try:
                                        pages = [
                                            int(p.strip())
                                            for p in b["pages"].split(",")
                                        ]
                                    except ValueError:
                                        pages = []

                            # Make sure all pages are integers
                            pages = [
                                int(p) if not isinstance(p, int) else p for p in pages
                            ]

                        normalized.append(
                            {
                                "product": b.get("product", "Unnamed Product"),
                                "pages": pages,
                                "confidence": confidence,
                                "reason": b.get("reason", ""),
                            }
                        )

                return normalized
            else:
                if self.debug:
                    print("No valid JSON found in response")
                return []
        except Exception as e:
            if self.debug:
                print(f"Error parsing boundaries: {str(e)}")
            return []

    def extract_and_print(self, pdf_path: str) -> None:
        """
        Extract technical sheets and print the results.

        Args:
            pdf_path: Path to the PDF file
        """
        if self.debug:
            print(f"\nAnalyzing {pdf_path} for technical sheets")

        # Process with LLM
        response = self.ocr_analyzer.process_file(pdf_path)

        # Parse boundaries from response
        sheets = self._parse_boundaries(response)

        if self.debug:
            print(f"Found {len(sheets)} technical sheets")
            for s in sheets:
                print(
                    f"Product: {s.get('product')} (confidence: {s.get('confidence', 0.0):.2f})"
                )
                print(f"  Pages: {s.get('pages')}")
                print(f"  Reason: {s.get('reason')}\n")

    def extract_sheets(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extract technical sheet boundaries from a PDF catalog.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of technical sheet dictionaries with boundaries
        """
        if self.debug:
            print(f"\nAnalyzing {pdf_path} for technical sheets")

        # Process with LLM

        # document_analysis = self.get_document_analysis(pdf_path)
        enhanced_pdf_path, analysis_path, document_analysis, tech_sheet_pages = document_processor_main(pdf_path)

        response = self.ocr_analyzer.process_file(enhanced_pdf_path, document_analysis)

        # Store response for debugging
        self.last_response = response

        # Parse boundaries from response
        sheets = self._parse_boundaries(response)

        # Store detected technical sheet pages for reference
        self.tech_sheet_pages = set()
        for sheet in sheets:
            for page in sheet.get("pages", []):
                self.tech_sheet_pages.add(page)

        return sheets

    def get_document_analysis(self, pdf_path: str) -> Dict[str, Any]:
        """
        Perform basic document analysis to provide metadata for LLM processing.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary with document metadata and structure
        """
        try:
            # Open the PDF
            doc = fitz.open(pdf_path)

            # Extract basic document information
            document_info = {
                "filename": os.path.basename(pdf_path),
                "page_count": len(doc),
                "metadata": doc.metadata,
                "has_toc": bool(doc.get_toc()),
                "pages": [],
            }

            # Extract information about each page
            for page_num, page in enumerate(doc):
                # Basic page info
                page_info = {
                    "page_number": page_num + 1,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "rotation": page.rotation,
                }

                # Try to extract text (first 500 chars for preview)
                text = page.get_text()
                page_info["has_text"] = bool(text.strip())
                page_info["text_preview"] = (
                    text[:500] + "..." if len(text) > 500 else text
                )

                # Image count
                image_list = page.get_images(full=False)
                page_info["image_count"] = len(image_list)

                # Check for page labels/numbers in the document
                if hasattr(page, "get_label"):
                    page_info["label"] = page.get_label()

                document_info["pages"].append(page_info)

            doc.close()
            return document_info

        except Exception as e:
            if self.debug:
                print(f"Error analyzing document: {str(e)}")
            return {"filename": os.path.basename(pdf_path), "error": str(e)}

    def extract_sheets_to_pdf(self, pdf_path: str) -> List[str]:
        """
        Extract technical sheets from a PDF catalog and save each sheet as a separate PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of paths to the extracted PDF files
        """
        if self.debug:
            print(f"\nProcessing {pdf_path} for extraction")

        # Get sheets information using extract_sheets instead of direct process_file
        sheets = self.extract_sheets(pdf_path)

        if self.debug:
            print(f"Found {len(sheets)} technical sheets")

        if not sheets:
            if self.debug:
                print("No technical sheets found to extract")
            return []

        # Create output directory for this catalog
        catalog_name = Path(pdf_path).stem
        output_subdir = os.path.join(self.output_dir, f"{catalog_name}_sheets")
        os.makedirs(output_subdir, exist_ok=True)

        # Open the PDF
        doc = fitz.open(pdf_path)
        extracted_paths = []

        # Process each technical sheet
        for i, sheet in enumerate(sheets):
            product_name = sheet.get("product", f"Product_{i + 1}")
            page_list = sheet.get("pages", [])

            # Skip if no pages defined
            if not page_list:
                if self.debug:
                    print(f"Skipping '{product_name}' - no pages defined")
                continue

            # Sort and validate pages (1-indexed to 0-indexed)
            page_list = sorted([p - 1 for p in page_list if p > 0 and p <= len(doc)])

            if not page_list:
                if self.debug:
                    print(f"Skipping '{product_name}' - no valid pages")
                continue

            # Create a new PDF for this technical sheet
            new_doc = fitz.open()

            # Copy pages from original document
            for page_num in page_list:
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)

            # Sanitize product name for filename
            safe_name = "".join(
                c if c.isalnum() or c in " -_" else "_" for c in product_name
            )
            safe_name = safe_name.strip().replace(" ", "_")

            # Truncate long names
            if len(safe_name) > 50:
                safe_name = safe_name[:47] + "..."

            # Create output filename with page range and confidence
            page_range = f"p{min(page_list) + 1}-{max(page_list) + 1}"
            if len(page_list) == 1:
                page_range = f"p{page_list[0] + 1}"

            # Include first page in filename for easier identification
            first_page = min(page_list) + 1
            output_filename = f"sheet_{first_page}_{safe_name}_{page_range}_conf{sheet.get('confidence', 0.5):.2f}.pdf"
            output_path = os.path.join(output_subdir, output_filename)

            # Save the new PDF
            new_doc.save(output_path)
            new_doc.close()

            extracted_paths.append(output_path)

            if self.debug:
                print(
                    f"Extracted '{product_name}' to {output_path} (pages {[p + 1 for p in page_list]})"
                )

        # Close the original document
        doc.close()

        if self.debug:
            print(
                f"Extracted {len(extracted_paths)} technical sheets to {output_subdir}"
            )

        return extracted_paths


@app.local_entrypoint()
def main():
    # Example usage
    pdf_filename_tertu_1_10 = "data/input/Catalogue-Tertu-Equipements-1-10.pdf"
    pdf_filename_tertu_1_25 = "data/input/Catalogue-Tertu-Equipements-1-25.pdf"
    pdf_filename_bordures = "data/input/CEL_Bordures_12-2020_V2.pdf"

    # Initialize pipeline
    # mistral_api_key = os.environ.get("MISTRAL_API_KEY")
    mistral_api_key = "IwkFyXMZh3thViQIWVgwtpaG3JXjzhlj"
    pipeline = Pipeline(
        mistral_api_key=mistral_api_key,
        llm_model="mistral-small-latest",
        confidence_threshold=0.6,
        debug=True,
        output_dir="output",
    )

    extracted_paths = pipeline.extract_sheets_to_pdf(pdf_filename_tertu_1_10)
    print(f"\nExtracted {len(extracted_paths)} technical sheets as separate PDF files.")
    print("Paths to extracted files:")
    for path in extracted_paths:
        print(f"- {path}")
