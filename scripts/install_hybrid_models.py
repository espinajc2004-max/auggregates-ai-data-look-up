"""
Installation script for Hybrid Mistral+T5 Architecture.

This script:
1. Checks Python dependencies
2. Verifies GPU availability
3. Downloads Mistral 7B model
4. Checks for T5 model or provides instructions
5. Tests model loading
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def check_dependencies():
    """Check if required Python packages are installed."""
    print_header("Step 1: Checking Python Dependencies")
    
    required_packages = [
        "torch",
        "transformers",
        "accelerate",
        "bitsandbytes"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} is installed")
        except ImportError:
            print(f"✗ {package} is NOT installed")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("\nInstalling missing packages...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("\n✓ All dependencies installed!")
    else:
        print("\n✓ All dependencies are installed!")
    
    return True


def check_gpu():
    """Check GPU availability."""
    print_header("Step 2: Checking GPU Availability")
    
    try:
        import torch
        
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            
            print(f"✓ CUDA is available")
            print(f"  GPU: {gpu_name}")
            print(f"  Memory: {gpu_memory:.2f} GB")
            
            if gpu_memory < 6:
                print(f"\n⚠️  Warning: GPU has only {gpu_memory:.2f} GB memory")
                print("   Mistral 7B with 8-bit quantization requires at least 6GB")
                print("   Consider using 4-bit quantization or CPU (very slow)")
            else:
                print(f"\n✓ GPU has sufficient memory for 8-bit quantization")
            
            return True
        else:
            print("✗ CUDA is NOT available")
            print("\n⚠️  No GPU detected. Models will run on CPU (very slow)")
            print("   For production, you need a GPU with at least 6GB VRAM")
            return False
            
    except Exception as e:
        print(f"✗ Error checking GPU: {e}")
        return False


def download_mistral():
    """Download Mistral 7B model."""
    print_header("Step 3: Downloading Mistral 7B Model")
    
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        
        model_name = "mistralai/Mistral-7B-Instruct-v0.1"
        
        print(f"Downloading {model_name}...")
        print("This will download ~14GB and may take several minutes...")
        print("(Model will be cached in ~/.cache/huggingface/)\n")
        
        # Download tokenizer
        print("Downloading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        print("✓ Tokenizer downloaded")
        
        # Download model (this will cache it)
        print("\nDownloading model (this may take a while)...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto",
            torch_dtype="auto"
        )
        print("✓ Model downloaded and cached")
        
        # Clean up to free memory
        del model
        del tokenizer
        
        print("\n✓ Mistral 7B model is ready!")
        return True
        
    except Exception as e:
        print(f"✗ Error downloading Mistral: {e}")
        print("\nYou can try downloading manually later.")
        print("The model will auto-download on first use.")
        return False


def check_t5_model():
    """Check if T5 model exists."""
    print_header("Step 4: Checking T5 Model")
    
    t5_path = os.getenv("T5_MODEL_PATH", "gaussalgo/T5-LM-Large-text2sql-spider")
    
    # For HuggingFace model IDs, try loading directly
    is_hf_model = "/" in t5_path and not os.path.exists(t5_path)
    
    if os.path.exists(t5_path) or is_hf_model:
        print(f"✓ T5 model path: {t5_path}")
        
        # Try to load it
        try:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            
            print("  Testing T5 model loading...")
            tokenizer = AutoTokenizer.from_pretrained(t5_path)
            model = AutoModelForSeq2SeqLM.from_pretrained(t5_path)
            
            print("✓ T5 model loads successfully!")
            
            # Clean up
            del model
            del tokenizer
            
            return True
            
        except Exception as e:
            print(f"✗ Error loading T5 model: {e}")
            if is_hf_model:
                print("  The model could not be downloaded from HuggingFace")
                print("  Check your internet connection and model identifier")
            else:
                print("  The model directory exists but may be corrupted")
            return False
    else:
        print(f"✗ T5 model NOT found at: {t5_path}")
        print("\n" + "─" * 60)
        print("T5 MODEL SETUP REQUIRED")
        print("─" * 60)
        print("\nRecommended: Use the pre-trained Spider text-to-SQL model:")
        print("   Set T5_MODEL_PATH=gaussalgo/T5-LM-Large-text2sql-spider in your .env file")
        print("   This model is pre-trained on the Spider dataset and requires no custom training")
        print("   It will be downloaded automatically from HuggingFace (~770MB)")
        print("\nAlternatively:")
        print("   - Set T5_MODEL_PATH to a local directory containing a compatible T5 model")
        print("   - Or set T5_MODEL_PATH to another HuggingFace model identifier")
        print("\n" + "─" * 60)
        
        return False


def test_hybrid_service():
    """Test the hybrid service initialization."""
    print_header("Step 5: Testing Hybrid Service")
    
    try:
        print("Testing service imports...")
        
        # Test imports
        from app.services.mistral_service import MistralService
        from app.config.mistral_config import MistralConfig
        
        print("✓ Service imports successful")
        
        print("\nNote: Full model loading test skipped to save time.")
        print("Models will be loaded when you first use the service.")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing service: {e}")
        return False


def create_env_template():
    """Create .env template if it doesn't exist."""
    print_header("Step 6: Environment Configuration")
    
    env_file = Path(".env")
    
    if env_file.exists():
        print("✓ .env file already exists")
    else:
        print("Creating .env template...")
        
        template = """# Mistral Configuration
MISTRAL_MODEL=mistralai/Mistral-7B-Instruct-v0.1
MISTRAL_QUANTIZATION=8bit
MISTRAL_TEMPERATURE=0.1
MISTRAL_MAX_TOKENS=512

# T5 Configuration
T5_MODEL_PATH=gaussalgo/T5-LM-Large-text2sql-spider

# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/construction_db
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Logging
LOG_LEVEL=INFO
"""
        
        env_file.write_text(template)
        print("✓ .env template created")
        print("  Please update with your actual configuration")


def main():
    """Main installation flow."""
    print("\n" + "=" * 60)
    print("  HYBRID MISTRAL+T5 ARCHITECTURE INSTALLATION")
    print("  Stage 1: Mistral (Intent Understanding)")
    print("  Stage 2: T5 (SQL Generation)")
    print("  Stage 3: Mistral (Response Formatting)")
    print("=" * 60)
    
    results = {
        "dependencies": False,
        "gpu": False,
        "mistral": False,
        "t5": False,
        "service": False
    }
    
    # Run installation steps
    results["dependencies"] = check_dependencies()
    results["gpu"] = check_gpu()
    
    if results["dependencies"]:
        results["mistral"] = download_mistral()
        results["t5"] = check_t5_model()
        results["service"] = test_hybrid_service()
    
    create_env_template()
    
    # Summary
    print_header("Installation Summary")
    
    print("Status:")
    print(f"  Dependencies: {'✓' if results['dependencies'] else '✗'}")
    print(f"  GPU: {'✓' if results['gpu'] else '✗ (will use CPU)'}")
    print(f"  Mistral 7B: {'✓' if results['mistral'] else '⚠️  (will download on first use)'}")
    print(f"  T5 Model: {'✓' if results['t5'] else '✗ (needs setup)'}")
    print(f"  Service: {'✓' if results['service'] else '✗'}")
    
    if all([results["dependencies"], results["t5"]]):
        print("\n" + "=" * 60)
        print("  ✓ INSTALLATION COMPLETE!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Update .env with your database credentials")
        print("2. Test the hybrid service:")
        print("   python test_hybrid_service.py")
        print("3. Start the API server:")
        print("   uvicorn app.main:app --reload")
        print("4. Test the endpoint:")
        print("   POST http://localhost:8000/api/chat/hybrid")
    else:
        print("\n" + "=" * 60)
        print("  ⚠️  INSTALLATION INCOMPLETE")
        print("=" * 60)
        print("\nPlease address the issues above before proceeding.")
        
        if not results["t5"]:
            print("\n⚠️  CRITICAL: T5 model is required for the hybrid architecture")
            print("   Set T5_MODEL_PATH=gaussalgo/T5-LM-Large-text2sql-spider in .env")
            print("   See Step 4 output for setup instructions")


if __name__ == "__main__":
    main()
