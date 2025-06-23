import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "localhost")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_DEBUG: bool = os.getenv("API_DEBUG", "False").lower() == "true"
    
    # Mistral AI Configuration
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
    MISTRAL_MODEL_NAME: str = os.getenv("MISTRAL_MODEL_NAME", "mistral-small-latest")
    MISTRAL_OCR: str = os.getenv("MISTRAL_OCR", "mistral-ocr-latest")
    
    # Storage Configuration
    CATALOG_DIR: str = os.getenv("CATALOG_DIR", "../data/catalogs")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "../data/output")
    OUTPUT_STREAMLIT_DIR: str = os.getenv("OUTPUT_STREAMLIT_DIR", "../data/output_streamlit")
    
    def validate(self):
        """Validate required configuration"""
        if not self.MISTRAL_API_KEY:
            raise ValueError("MISTRAL_API_KEY is required in environment variables")
        
        # Create directories if they don't exist
        os.makedirs(self.CATALOG_DIR, exist_ok=True)
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        
        if self.API_PORT < 1 or self.API_PORT > 65535:
            raise ValueError("API_PORT must be between 1 and 65535")

        print("Configuration validated successfully.")

# Create global config instance
config = Config()
config.validate()  # Validate on import