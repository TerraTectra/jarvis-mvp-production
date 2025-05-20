"""Wait for model to download and run tests."""
import os
import time
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def is_model_downloaded() -> bool:
    """Check if the model file exists and has a reasonable size (>100MB)."""
    model_path = Path("models/mistral/mistral-7b-instruct-v0.2.Q4_K_M.gguf")
    if not model_path.exists():
        return False
    
    # Check if file size is reasonable (>100MB)
    size_mb = model_path.stat().st_size / (1024 * 1024)
    if size_mb < 100:
        logger.warning(f"Model file is too small: {size_mb:.2f}MB")
        return False
    
    return True

def run_tests():
    """Run the LLM integration tests."""
    logger.info("🚀 Starting LLM integration tests...")
    try:
        # Run the test script
        result = subprocess.run(
            ["python", "-m", "scripts.test_llm_integration"],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Log the output
        logger.info("Test output:\n" + result.stdout)
        if result.stderr:
            logger.error("Test errors:\n" + result.stderr)
            
        logger.info("✅ Tests completed successfully!")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Tests failed with exit code {e.returncode}:")
        logger.error(e.stderr)
    except Exception as e:
        logger.error(f"❌ Error running tests: {e}")

def main():
    """Main function to wait for model and run tests."""
    logger.info("🕒 Waiting for model to be fully downloaded...")
    
    # Wait for model to be downloaded
    while not is_model_downloaded():
        logger.info("Model not ready, checking again in 30 seconds...")
        time.sleep(30)
    
    logger.info("✅ Model is ready!")
    
    # Run the tests
    run_tests()

if __name__ == "__main__":
    main()
