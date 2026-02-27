"""
Upload T5 fine-tuned model to HuggingFace.
Run: python upload_t5_to_hf.py
"""
import os
import subprocess
import sys
import time

# Install huggingface_hub if not present
try:
    from huggingface_hub import HfApi
except ImportError:
    print("Installing huggingface_hub...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub"])
    from huggingface_hub import HfApi

TOKEN = os.getenv("HF_TOKEN")
if not TOKEN:
    print("ERROR: Set HF_TOKEN environment variable first.")
    print("  Windows: set HF_TOKEN=hf_your_token_here")
    print("  Linux:   export HF_TOKEN=hf_your_token_here")
    sys.exit(1)
REPO_ID = "espinajc/t5-auggregates-text2sql"
MODEL_PATH = r"C:\models\t5-finetuned"

api = HfApi()

# Step 1: Create the repo if it doesn't exist
print("Step 1: Creating HuggingFace repo (if not exists)...")
try:
    api.create_repo(repo_id=REPO_ID, repo_type="model", token=TOKEN, exist_ok=True)
    print(f"Repo ready: https://huggingface.co/{REPO_ID}\n")
except Exception as e:
    print(f"Repo creation error: {e}")
    exit(1)

# Step 2: Upload with retry logic
print("Step 2: Uploading model files...")
print("This will take 10-30 minutes (3.1GB model file).\n")

MAX_RETRIES = 3
for attempt in range(1, MAX_RETRIES + 1):
    try:
        print(f"Attempt {attempt}/{MAX_RETRIES}...")
        api.upload_folder(
            folder_path=MODEL_PATH,
            repo_id=REPO_ID,
            repo_type="model",
            token=TOKEN
        )
        print(f"\nDone! Check: https://huggingface.co/{REPO_ID}")
        break
    except Exception as e:
        print(f"\nAttempt {attempt} failed: {e}")
        if attempt < MAX_RETRIES:
            wait = 30 * attempt
            print(f"Retrying in {wait} seconds... (LFS files already uploaded, only commit will retry)")
            time.sleep(wait)
        else:
            print("\nAll retries failed.")
            print("Check if files are already on HF: https://huggingface.co/espinajc/t5-auggregates-text2sql")
            print("If files are there, upload was successful despite the error.")
