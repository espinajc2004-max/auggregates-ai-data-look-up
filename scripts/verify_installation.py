"""
Verification script to check if all dependencies are installed correctly.
"""
import sys

def check_pytorch():
    """Check PyTorch installation and CUDA availability."""
    try:
        import torch
        print("✅ PyTorch installed")
        print(f"   Version: {torch.__version__}")
        print(f"   CUDA Available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"   CUDA Version: {torch.version.cuda}")
            print(f"   GPU Name: {torch.cuda.get_device_name(0)}")
            print(f"   GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
        else:
            print("   ⚠️  WARNING: CUDA not available. Training will be slow on CPU.")
            print("   Please install PyTorch with CUDA support:")
            print("   pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu118")
        return True
    except ImportError:
        print("❌ PyTorch not installed")
        return False

def check_transformers():
    """Check Transformers installation."""
    try:
        import transformers
        print(f"✅ Transformers installed (version: {transformers.__version__})")
        return True
    except ImportError:
        print("❌ Transformers not installed")
        return False

def check_datasets():
    """Check Datasets installation."""
    try:
        import datasets
        print(f"✅ Datasets installed (version: {datasets.__version__})")
        return True
    except ImportError:
        print("❌ Datasets not installed")
        return False

def check_accelerate():
    """Check Accelerate installation."""
    try:
        import accelerate
        print(f"✅ Accelerate installed (version: {accelerate.__version__})")
        return True
    except ImportError:
        print("❌ Accelerate not installed")
        return False

def check_sentencepiece():
    """Check SentencePiece installation."""
    try:
        import sentencepiece
        print(f"✅ SentencePiece installed")
        return True
    except ImportError:
        print("❌ SentencePiece not installed")
        return False

def check_sklearn():
    """Check scikit-learn installation."""
    try:
        import sklearn
        print(f"✅ scikit-learn installed (version: {sklearn.__version__})")
        return True
    except ImportError:
        print("❌ scikit-learn not installed")
        return False

def check_nltk():
    """Check NLTK installation."""
    try:
        import nltk
        print(f"✅ NLTK installed (version: {nltk.__version__})")
        return True
    except ImportError:
        print("❌ NLTK not installed")
        return False

def check_evaluate():
    """Check Evaluate installation."""
    try:
        import evaluate
        print(f"✅ Evaluate installed")
        return True
    except ImportError:
        print("❌ Evaluate not installed")
        return False

def main():
    """Run all checks."""
    print("=" * 60)
    print("Verifying Installation for T5 Text-to-SQL Training")
    print("=" * 60)
    print()
    
    checks = [
        check_pytorch,
        check_transformers,
        check_datasets,
        check_accelerate,
        check_sentencepiece,
        check_sklearn,
        check_nltk,
        check_evaluate,
    ]
    
    results = [check() for check in checks]
    
    print()
    print("=" * 60)
    if all(results):
        print("✅ All dependencies installed successfully!")
        print()
        print("Next Steps:")
        print("1. Generate training data: python ml/training/generate_t5_training_data.py")
        print("2. Train T5 model: python ml/training/train_t5_text_to_sql.py")
    else:
        print("❌ Some dependencies are missing. Please install them:")
        print("   Run: pip install -r requirements_t5.txt")
        print("   Or: scripts\\install_dependencies.bat")
        sys.exit(1)
    print("=" * 60)

if __name__ == "__main__":
    main()
