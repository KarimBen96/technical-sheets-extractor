import sys
import os
import json
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF
from pathlib import Path
from datetime import datetime

from mistralai import Mistral
        
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def check_mistral_api(api_key: Optional[str] = None) -> bool:
    """Check if Mistral API key is working with a simple test call."""
    try:
        # if api_key is None:
        #     api_key = os.getenv('MISTRAL_API_KEY')
        client = Mistral(api_key)
        response = client.chat.complete(
            model="mistral-tiny",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5
        )
        return True
    except:
        return False



if __name__ == "__main__":
    mistral_api_key = "IwkFyXMZh3thViQIWVgwtpaG3JXjzhlj"

    check_result = check_mistral_api(mistral_api_key)
    if check_result:
        print("Mistral API key is working.")
    else:
        print("Mistral API key is not working.")
