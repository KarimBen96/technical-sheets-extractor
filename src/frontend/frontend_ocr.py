import os
import sys
import json
import streamlit as st
import base64
import pandas as pd
from pdf2image import convert_from_path
import io
from PyPDF2 import PdfReader
import zipfile

# Add parent directory to path to import the pipeline module
# This is important for Modal deployment
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import components
try:
    from utils.config import Config
    from ai_processor.pipeline import Pipeline
except ImportError as e:
    st.error(f"Failed to import Pipeline: {e}")
    st.error(f"Python path: {sys.path}")
    st.error(f"Current directory: {os.getcwd()}")
    st.stop()

# Import configuration
CATALOG_DIR = Config.CATALOG_DIR
OUTPUT_STREAMLIT_DIR = Config.OUTPUT_STREAMLIT_DIR

llm_model = Config.MISTRAL_MODEL_NAME


# Set page configuration, title
st.set_page_config(page_title="PDF Technical Sheets Extractor", layout="wide")
st.title("PDF Technical Sheet Extractor")


# Get API key from environment
api_key = os.environ.get("MISTRAL_API_KEY")
if not api_key:
    st.error("❌ MISTRAL_API_KEY not found in environment variables!")
    st.info("Ensure the .env file contains MISTRAL_API_KEY=your_key_here")
    st.stop()


def safe_file_operation(file_path, operation="read"):
    """Safely perform file operations with error handling."""
    try:
        if operation == "read":
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    return f.read()
        elif operation == "exists":
            return os.path.exists(file_path)
        elif operation == "size":
            return os.path.getsize(file_path) if os.path.exists(file_path) else 0
    except Exception:
        return None


def get_image_as_base64(image_path_or_pil):
    """Convert image to base64 string for direct display in Streamlit."""
    try:
        if isinstance(image_path_or_pil, str):
            with open(image_path_or_pil, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
        else:
            buffer = io.BytesIO()
            image_path_or_pil.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode()
    except Exception as e:
        st.error(f"Error converting image to base64: {e}")
        return None


def display_page_image_base64(pdf_path, page_num, dpi=150):
    """Display a specific page of a PDF as an image using base64."""
    try:
        if not os.path.exists(pdf_path):
            st.error(f"PDF file not found: {pdf_path}")
            return None

        pdf = PdfReader(pdf_path)
        total_pages = len(pdf.pages)

        if page_num < 0 or page_num >= total_pages:
            st.warning(
                f"Page {page_num + 1} is out of range (PDF has {total_pages} pages)"
            )
            return None

        images = convert_from_path(
            pdf_path, dpi=dpi, first_page=page_num + 1, last_page=page_num + 1
        )

        if images and len(images) > 0:
            base64_str = get_image_as_base64(images[0])
            if base64_str:
                return f"data:image/png;base64,{base64_str}"
        return None
    except Exception as e:
        st.error(f"Error processing PDF page {page_num + 1}: {str(e)}")
        return None


def visualize_technical_sheets(tech_sheets, total_pages):
    """Create a visualization of where technical sheets appear in the document."""
    timeline_data = []

    for sheet in tech_sheets:
        product = sheet.get("product", "Unknown")
        pages = sheet.get("pages", [])

        # Handle different page formats
        if isinstance(pages, str):
            try:
                pages = json.loads(pages.replace("'", '"'))
            except Exception as e:
                pages = [
                    int(p.strip()) for p in pages.strip("[]").split(",") if p.strip()
                ]
                print(f"Error parsing pages: {e}")

        for page in pages:
            timeline_data.append({"Page": int(page), "Product": product})

    if not timeline_data:
        st.warning("No technical sheet page data found in the analysis.")
        return

    df = pd.DataFrame(timeline_data)

    # Create summary
    summary_df = (
        df.groupby("Product")
        .agg(Pages=("Page", lambda x: sorted(list(x))))
        .reset_index()
    )
    summary_df["Page Count"] = summary_df["Pages"].apply(len)

    st.dataframe(summary_df[["Product", "Pages"]], use_container_width=True)


# # File upload section
# st.markdown("### PDF Document Upload")

# Add sample file option for testing
col1 = st.columns(1)[0]

with col1:
    uploaded_file = st.file_uploader(
        "Choose a PDF file", type=["pdf"], help="Select a PDF file to process"
    )

permanent_pdf_path = None

# Handle uploaded file
if uploaded_file is not None:
    try:
        # Save to uploads directory
        permanent_pdf_path = os.path.join(CATALOG_DIR, f"upload_{uploaded_file.name}")
        with open(permanent_pdf_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        file_size = len(uploaded_file.getvalue())
        st.success(f"File uploaded: {uploaded_file.name} ({file_size:,} bytes)")
    except Exception as e:
        st.error(f"Upload error: {e}")
        st.exception(e)
        permanent_pdf_path = None

# Process if we have a PDF
if permanent_pdf_path and os.path.exists(permanent_pdf_path):
    try:
        pdf = PdfReader(permanent_pdf_path)
        total_pages = len(pdf.pages)
        st.info(f"📄 Document has {total_pages} pages")

        st.write("")
        st.write("")
        st.write("")

        process_button = st.button(
            "Extract Technical Sheets", use_container_width=False, type="primary"
        )

        st.write("")
        st.write("")
        st.write("")

        if process_button:
            progress_bar = st.progress(0)
            status_text = st.empty()

            with st.spinner("Processing PDF..."):
                try:
                    # Initialize pipeline
                    status_text.text("Initializing AI pipeline...")
                    progress_bar.progress(10)

                    pipeline = Pipeline(
                        mistral_api_key=api_key,
                        llm_model=llm_model,
                        output_dir=OUTPUT_STREAMLIT_DIR,
                    )

                    # Extract sheets
                    status_text.text("Analyzing document structure...")
                    progress_bar.progress(30)
                    boundaries = pipeline.extract_sheets(permanent_pdf_path)

                    status_text.text("Extracting technical sheets...")
                    progress_bar.progress(60)
                    extracted_paths = pipeline.extract_sheets_to_pdf(permanent_pdf_path)

                    status_text.text("Getting document analysis...")
                    progress_bar.progress(80)
                    document_analysis = pipeline.get_document_analysis(
                        permanent_pdf_path
                    )

                    # Store results in session state
                    st.session_state.boundaries = boundaries
                    st.session_state.document_analysis = document_analysis
                    st.session_state.extracted_paths = extracted_paths
                    st.session_state.original_pdf = permanent_pdf_path
                    st.session_state.processed = True
                    st.session_state.total_pages = total_pages

                    progress_bar.progress(100)
                    status_text.text("Processing complete!")

                except Exception as e:
                    st.error(f"Error processing PDF: {str(e)}")
                    st.exception(e)
                finally:
                    progress_bar.empty()
                    status_text.empty()

        # Display results if processing is complete
        if "processed" in st.session_state and st.session_state.processed:
            st.markdown("---")
            st.markdown("### Extraction Results")

            # Add download all button
            if (
                "extracted_paths" in st.session_state
                and st.session_state.extracted_paths
            ):
                col1, col2 = st.columns([1, 4])
                with col1:
                    # Create ZIP file in memory
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                        for pdf_path in st.session_state.extracted_paths:
                            pdf_data = safe_file_operation(pdf_path, "read")
                            if pdf_data:
                                filename = os.path.basename(pdf_path)
                                zipf.writestr(filename, pdf_data)

                    zip_data = zip_buffer.getvalue()
                    if zip_data:
                        st.download_button(
                            label="📦 Download All PDFs",
                            data=zip_data,
                            file_name="technical_sheets.zip",
                            mime="application/zip",
                        )

            if (
                "boundaries" in st.session_state
                and len(st.session_state.boundaries) > 0
            ):
                boundaries = st.session_state.boundaries

                # Show visualization
                st.markdown("#### Technical Sheets Overview")
                visualize_technical_sheets(boundaries, st.session_state.total_pages)

                # Show individual sheets
                st.markdown("#### Extracted Technical Sheets")

                for i, boundary in enumerate(boundaries):
                    with st.expander(
                        f"📄 {boundary.get('product', f'Technical Sheet {i + 1}')}"
                    ):
                        col1, col2 = st.columns([1, 3])

                        with col1:
                            st.write("**Detection Reason:**")
                            st.write(boundary.get("reason", "Not provided"))

                            # Download button for extracted PDF
                            pages = boundary.get("pages", [])
                            if isinstance(pages, str):
                                try:
                                    pages = json.loads(pages.replace("'", '"'))
                                except Exception:
                                    pages = [
                                        int(p.strip())
                                        for p in pages.strip("[]").split(",")
                                        if p.strip()
                                    ]

                            # Find corresponding PDF file
                            if (
                                "extracted_paths" in st.session_state
                                and st.session_state.extracted_paths
                            ):
                                matching_pdf = None
                                first_page = pages[0] if pages else i + 1

                                for pdf_path in st.session_state.extracted_paths:
                                    if f"sheet_{first_page}_" in os.path.basename(
                                        pdf_path
                                    ):
                                        matching_pdf = pdf_path
                                        break

                                if matching_pdf and safe_file_operation(
                                    matching_pdf, "exists"
                                ):
                                    pdf_data = safe_file_operation(matching_pdf, "read")
                                    if pdf_data:
                                        # Clean product name for filename
                                        product_name = boundary.get(
                                            "product", f"sheet_{i}"
                                        )
                                        safe_name = "".join(
                                            c if c.isalnum() or c in " -_" else "_"
                                            for c in product_name
                                        )
                                        safe_name = safe_name.strip().replace(" ", "_")[
                                            :50
                                        ]

                                        st.download_button(
                                            label="📥 Download PDF",
                                            data=pdf_data,
                                            file_name=f"{safe_name}.pdf",
                                            mime="application/pdf",
                                            key=f"download_{i}",
                                        )
                                    else:
                                        st.warning("Could not read PDF file")
                                else:
                                    st.warning("PDF file not found")
                            else:
                                st.warning("No extracted PDFs available")

                        with col2:
                            pages = boundary.get("pages", [])
                            if isinstance(pages, str):
                                try:
                                    pages = json.loads(pages.replace("'", '"'))
                                except Exception as e:
                                    pages = [
                                        int(p.strip())
                                        for p in pages.strip("[]").split(",")
                                        if p.strip()
                                    ]
                                    print(f"Error parsing pages: {e}")

                            if pages:
                                st.write(
                                    f"**Pages:** {', '.join(str(p) for p in pages)}"
                                )

                                # Show page thumbnails
                                thumb_cols = st.columns(min(len(pages), 4))
                                for j, page_num in enumerate(
                                    pages[:4]
                                ):  # Show max 4 thumbnails
                                    col_idx = j % len(thumb_cols)
                                    with thumb_cols[col_idx]:
                                        image_base64 = display_page_image_base64(
                                            st.session_state.original_pdf,
                                            page_num - 1,
                                            dpi=75,
                                        )
                                        if image_base64:
                                            st.markdown(
                                                f'''
                                                <div style="text-align: center;">
                                                    <img src="{image_base64}" width="150" style="border: 1px solid #ddd; border-radius: 4px;">
                                                    <p style="font-size: 12px; margin-top: 5px;">Page {page_num}</p>
                                                </div>
                                                ''',
                                                unsafe_allow_html=True,
                                            )
                                        else:
                                            st.error(f"Failed to load page {page_num}")
            else:
                st.info("No technical sheets were detected in this document.")

    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        st.exception(e)
