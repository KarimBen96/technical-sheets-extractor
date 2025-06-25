import subprocess
from pathlib import Path
import os
import sys
import tempfile
from dotenv import load_dotenv

import modal

streamlit_script_local_path = Path(__file__).parent / "src/frontend/frontend_ocr.py"
# streamlit_script_local_path = Path(__file__).parent / "frontend_ocr.py"
streamlit_script_remote_path = "/root/frontend/frontend_ocr.py"
# streamlit_script_remote_path = "/root/frontend_ocr.py"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements("requirements.txt")
    .apt_install("poppler-utils", "locales")
    .run_commands("locale-gen en_US.UTF-8")
    .env({"LC_ALL": "en_US.UTF-8", "LANG": "en_US.UTF-8"})
    .add_local_dir("src/ai_processor", "/root/ai_processor")
    .add_local_dir("src/frontend", "/root/frontend")
    .add_local_dir("src/utils", "/root/utils")
    .add_local_file(".env", "/root/.env")
    .add_local_file(
        streamlit_script_local_path,
        streamlit_script_remote_path,
    )
)


app = modal.App(name="technical-sheets-extractor-v1.1", image=image)


@app.function(image=image)
def debug_image():
    """Debug function to see what's inside the image"""
    import os
    from dotenv import load_dotenv

    print("=== ROOT DIRECTORY ===")
    for root, dirs, files in os.walk("/root"):
        level = root.replace("/root", "").count(os.sep)
        indent = " " * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        sub_indent = " " * 2 * (level + 1)
        for file in files:
            print(f"{sub_indent}{file}")

    print("\n=== .ENV FILE CONTENTS ===")
    load_dotenv("/root/.env")
    with open("/root/.env", "r") as f:
        print(f.read())


@app.function(image=image)
def debug_upload():
    """Simple debug to check upload setup"""

    print("=== DIRECTORIES ===")
    print(f"tempfile.gettempdir(): {tempfile.gettempdir()}")
    print(f"/tmp exists: {os.path.exists('/tmp')}")
    print(
        f"/tmp permissions: {oct(os.stat('/tmp').st_mode)[-3:] if os.path.exists('/tmp') else 'N/A'}"
    )

    print("\n=== STREAMLIT RELATED ENV VARS ===")
    for key, value in os.environ.items():
        if "STREAMLIT" in key or "TMP" in key:
            print(f"{key}: {value}")

    print("\n=== CURRENT WORKING DIR ===")
    print(f"Current dir: {os.getcwd()}")
    print(f"Contents: {os.listdir('.')}")


@app.function(image=image)
@modal.concurrent(max_inputs=100)  # Very important line
@modal.web_server(8000)
def run_streamlit():
    # Setup environment
    sys.path.insert(0, "/root")
    os.environ["CATALOG_DIR"] = "/root/data/catalogs"      
    os.environ["OUTPUT_DIR"] = "/root/data/output"       
    os.makedirs("/root/data/catalogs", exist_ok=True)
    os.makedirs("/root/data/output", exist_ok=True)
    # Encoding environment variables
    os.environ['LC_ALL'] = 'en_US.UTF-8'
    os.environ['LANG'] = 'en_US.UTF-8'
    os.environ['PYTHONIOENCODING'] = 'utf-8'

    load_dotenv("/root/.env")

    subprocess.Popen([
        "streamlit", "run", streamlit_script_remote_path,
        "--server.port", "8000",
        "--server.address", "0.0.0.0",
        "--server.enableXsrfProtection=false",
        "--server.maxUploadSize=200"
    ])