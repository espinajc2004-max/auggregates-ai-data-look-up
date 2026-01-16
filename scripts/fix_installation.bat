@echo off
echo ========================================
echo Fixing Installation - Installing Missing Dependencies
echo ========================================
echo.

echo Step 1: Uninstalling CPU version of PyTorch...
pip uninstall -y torch torchvision torchaudio

echo.
echo Step 2: Installing PyTorch with CUDA 11.8 support for RTX 3060...
echo This may take a few minutes...
pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu118

echo.
echo Step 3: Installing missing dependencies...
pip install datasets==2.16.0
pip install sentencepiece==0.1.99
pip install nltk==3.8.1
pip install evaluate==0.4.1
pip install sacrebleu==2.3.1

echo.
echo Step 4: Verifying installation...
python scripts/verify_installation.py

echo.
pause
