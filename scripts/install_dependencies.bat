@echo off
echo ========================================
echo Installing Dependencies for T5 Text-to-SQL
echo ========================================
echo.

echo Step 1: Installing PyTorch with CUDA 11.8 support...
pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu118

echo.
echo Step 2: Installing Transformers and related packages...
pip install transformers==4.36.0 sentencepiece==0.1.99 datasets==2.16.0 accelerate==0.25.0

echo.
echo Step 3: Installing additional training dependencies...
pip install scikit-learn==1.3.2 nltk==3.8.1 evaluate==0.4.1 sacrebleu==2.3.1

echo.
echo Step 4: Verifying GPU detection...
python -c "import torch; print('PyTorch Version:', torch.__version__); print('CUDA Available:', torch.cuda.is_available()); print('CUDA Version:', torch.version.cuda if torch.cuda.is_available() else 'N/A'); print('GPU Name:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Next Steps:
echo 1. Verify GPU detection above shows "CUDA Available: True"
echo 2. Run: python scripts/verify_installation.py
echo 3. Start training data generation: python ml/training/generate_t5_training_data.py
echo.
pause
