"""Script to download Mistral-7B-Instruct model."""
from huggingface_hub import hf_hub_download
import os

def download_model():
    """Download Mistral-7B-Instruct model."""
    model_path = "models/mistral"
    os.makedirs(model_path, exist_ok=True)
    
    print("Downloading Mistral-7B-Instruct-v0.2-GGUF...")
    
    try:
        # Download the model file
        model_path = hf_hub_download(
            repo_id="TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
            filename="mistral-7b-instruct-v0.2.Q4_K_M.gguf",
            local_dir=model_path,
            local_dir_use_symlinks=False
        )
        print(f"Model downloaded to: {model_path}")
    except Exception as e:
        print(f"Error downloading model: {e}")
        raise

if __name__ == "__main__":
    download_model()
