"""
GPU Verification Script for Phi-3 Migration
Checks CUDA availability and GPU memory requirements
"""

import sys

def check_gpu():
    """Check GPU availability and memory."""
    print("=" * 60)
    print("GPU Verification for Phi-3 Migration")
    print("=" * 60)
    
    # Check if torch is installed
    try:
        import torch
    except ImportError:
        print("\n❌ ERROR: PyTorch is not installed!")
        print("Please install dependencies first:")
        print("  pip install -r requirements.txt")
        return False
    
    # Check CUDA availability
    print(f"\n1. CUDA Available: {torch.cuda.is_available()}")
    
    if not torch.cuda.is_available():
        print("\n⚠️  WARNING: CUDA is not available!")
        print("This system does not have a compatible GPU.")
        print("\nOptions:")
        print("  - Install on a system with NVIDIA GPU")
        print("  - Use CPU-only mode (very slow, not recommended)")
        print("  - Deploy to a cloud instance with GPU")
        return False
    
    # Get GPU information
    gpu_count = torch.cuda.device_count()
    print(f"2. GPU Count: {gpu_count}")
    
    for i in range(gpu_count):
        gpu_name = torch.cuda.get_device_name(i)
        gpu_memory = torch.cuda.get_device_properties(i).total_memory / (1024**3)
        
        print(f"\n   GPU {i}: {gpu_name}")
        print(f"   Total Memory: {gpu_memory:.2f} GB")
        
        # Check memory requirements
        print("\n3. Memory Requirements Check:")
        print(f"   - Full precision (FP32): ~28GB (❌ Won't fit)")
        print(f"   - Half precision (FP16): ~14GB", end="")
        if gpu_memory >= 14:
            print(" (✅ Will fit)")
        else:
            print(" (❌ Won't fit)")
        
        print(f"   - 8-bit quantization: ~7GB", end="")
        if gpu_memory >= 7:
            print(" (✅ Will fit - RECOMMENDED)")
        else:
            print(" (❌ Won't fit)")
        
        print(f"   - 4-bit quantization: ~3.5GB", end="")
        if gpu_memory >= 3.5:
            print(" (✅ Will fit)")
        else:
            print(" (❌ Won't fit)")
        
        # Recommendation
        print("\n4. Recommendation:")
        if gpu_memory >= 14:
            print("   ✅ Your GPU has sufficient memory!")
            print("   Recommended: Use 8-bit quantization for best balance")
        elif gpu_memory >= 7:
            print("   ✅ Your GPU can run Phi-3 with 8-bit quantization")
        elif gpu_memory >= 3.5:
            print("   ⚠️  Your GPU can only run with 4-bit quantization")
            print("   Note: 4-bit may have reduced quality")
        else:
            print("   ❌ Your GPU has insufficient memory for Phi-3")
            print("   Minimum required: 2GB for 4-bit quantization")
            return False
    
    print("\n" + "=" * 60)
    print("✅ GPU verification complete!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = check_gpu()
    sys.exit(0 if success else 1)
