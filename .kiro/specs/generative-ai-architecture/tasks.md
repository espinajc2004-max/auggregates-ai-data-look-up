# Implementation Plan: Generative AI Architecture Migration

## Overview

This implementation plan guides the migration from the 3-stage architecture (DistilBERT + T5 + LoRA) to a simplified Mistral 7B generative AI approach. The migration follows a clean slate strategy: delete old code first, then install and implement the new system. The plan is organized into 5 phases executed over discrete, manageable coding steps.

## Migration Strategy

- **Approach**: Clean slate - remove old 3-stage code, install Mistral 7B, implement new services
- **Quantization**: Use 8-bit quantization to fit Mistral 7B in 14GB GPU
- **Reuse**: Keep existing utilities (conversation_db, schema_provider, sql_validator, results_formatter)
- **Testing**: Comprehensive unit tests, property tests, and integration tests throughout

## Tasks

- [x] 1. Phase 1: Backup and Cleanup
  - [x] 1.1 Create backup branch and export data
    - Create git backup branch `backup-3stage-architecture`
    - Backup database using existing backup scripts
    - Export conversation history to JSON
    - _Requirements: 15.3, 15.6_

  - [x] 1.2 Delete old 3-stage architecture code
    - Delete `app/services/stage1/` directory (orchestrator.py, db_clarification.py)
    - Delete `app/services/stage2/t5_sql_generator.py`
    - Delete `app/services/stage3/` directory (answer_composer.py, clarification_composer.py)
    - Delete obsolete service files: intent_router.py, context_aware_intent_detector.py, query_parser.py, semantic_extractor.py, semantic_extractor_v2.py, text_to_sql_service.py, router_service.py, embedding_service.py
    - _Requirements: 15.1, 15.4_

  - [x] 1.3 Delete training code and datasets
    - Delete entire `ml/training/` directory with all training scripts and datasets
    - Delete or archive old documentation (3STAGE_ARCHITECTURE.md, TRAINING_GUIDE.md)
    - Commit deletions with clear message
    - _Requirements: 15.4_

- [x] 2. Phase 2: Install Dependencies and Verify GPU
  - [x] 2.1 Update requirements.txt with Mistral dependencies
    - Add torch>=2.1.0, transformers>=4.36.0, accelerate>=0.25.0, bitsandbytes>=0.41.0
    - Add testing dependencies: hypothesis>=6.92.0, pytest-asyncio>=0.21.0
    - Install all dependencies with pip
    - _Requirements: 1.1, 1.2_

  - [x] 2.2 Verify GPU availability and memory
    - Write script to check CUDA availability
    - Verify GPU has at least 6GB memory for 8-bit quantization
    - Log GPU device name and total memory
    - Test torch.cuda operations
    - _Requirements: 1.2, 1.5, 10.1_

  - [ ]* 2.3 Pre-download Mistral 7B model (optional)
    - Download and cache Mistral 7B model from Hugging Face
    - Verify model files are cached in ~/.cache/huggingfac