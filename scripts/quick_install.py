"""
Quick installation script for Hybrid Mistral+T5 Architecture.
Skips problematic dependencies and focuses on core ML packages.
"""

import sys


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def check_core_dependencies():
    """Check if core ML packages are installed."""
    print_header("Checking Core ML Dependencies")
    
    packages = {
        "torch": "PyTorch",
        "transformers": "Hugging Face Transformers",
        "accelerate": "Accelerate",
        "bitsandbytes": "BitsAndBytes (quantization)"
    }
    
    all_installed = True
    for package, name in packages.items():
        try:
            __import__(package)
            print(f"✓ {name} is installed")
        except ImportError:
            print(f"✗ {name} is NOT installed")
            all_installed = False
    
    return all_installed


def check_gpu():
    """Check GPU availability."""
    print_header("Checking GPU")
    
    try:
        import torch
        
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            
            print(f"✓ CUDA is available")
            print(f"  GPU: {gpu_name}")
            print(f"  Memory: {gpu_memory:.2f} GB")
            
            if gpu_memory < 6:
                print(f"\n⚠️  Warning: Only {gpu_memory:.2f} GB available")
                print("   Mistral 7B with 8-bit quantization needs 6GB+")
                print("   Consider using 4-bit quantization or CPU (slow)")
            
            return True
        else:
            print("✗ No GPU detected")
            print("\n⚠️  Models will run on CPU (very slow)")
            print("   For production, use a GPU with 6GB+ VRAM")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def check_t5_model():
    """Check if T5 model exists."""
    print_header("Checking T5 Model")
    
    import os
    t5_path = os.getenv("T5_MODEL_PATH", "gaussalgo/T5-LM-Large-text2sql-spider")
    
    # Check if it's a local path that exists
    if os.path.exists(t5_path):
        print(f"✓ T5 model found locally at: {t5_path}")
        return True
    
    # For HuggingFace model identifiers, try to verify availability
    if "/" in t5_path:
        try:
            from transformers import AutoTokenizer
            AutoTokenizer.from_pretrained(t5_path, local_files_only=True)
            print(f"✓ T5 model cached locally: {t5_path}")
            return True
        except Exception:
            print(f"⚠️  T5 model not cached locally: {t5_path}")
            print(f"  The model will be downloaded from HuggingFace on first use")
            print(f"  To pre-download: python -c \"from transformers import AutoModelForSeq2SeqLM, AutoTokenizer; AutoTokenizer.from_pretrained('{t5_path}'); AutoModelForSeq2SeqLM.from_pretrained('{t5_path}')\"")
            return True
    
    print(f"✗ T5 model NOT found at: {t5_path}")
    print("\n" + "─" * 60)
    print("T5 MODEL REQUIRED")
    print("─" * 60)
    print("\nOptions:")
    print("1. Set T5_MODEL_PATH=gaussalgo/T5-LM-Large-text2sql-spider in .env")
    print("   (recommended — pre-trained on Spider text-to-SQL dataset)")
    print("2. Set T5_MODEL_PATH to a custom local model path")
    print("\n" + "─" * 60)
    return False


def main():
    """Main installation check."""
    print("\n" + "=" * 60)
    print("  HYBRID MISTRAL+T5 QUICK CHECK")
    print("=" * 60)
    
    results = {
        "ml_packages": check_core_dependencies(),
        "gpu": check_gpu(),
        "t5": check_t5_model()
    }
    
    print_header("Summary")
    
    print(f"ML Packages: {'✓' if results['ml_packages'] else '✗'}")
    print(f"GPU: {'✓' if results['gpu'] else '⚠️  (will use CPU)'}")
    print(f"T5 Model: {'✓' if results['t5'] else '✗'}")
    
    if results["ml_packages"] and results["t5"]:
        print("\n" + "=" * 60)
        print("  ✓ READY TO TEST!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Test the service:")
        print("   python test_hybrid_service.py")
        print("\n2. Start the API:")
        print("   uvicorn app.main:app --reload")
    else:
        print("\n" + "=" * 60)
        print("  ⚠️  NOT READY")
        print("=" * 60)
        
        if not results["ml_packages"]:
            print("\n✗ Install ML packages:")
            print("   python -m pip install torch transformers accelerate bitsandbytes")
        
        if not results["t5"]:
            print("\n✗ Setup T5 model (see options above)")


if __name__ == "__main__":
    main()
