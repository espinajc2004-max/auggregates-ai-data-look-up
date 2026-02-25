"""
T5 Fine-Tuning Script for Google Colab
========================================
Fine-tunes the T5-LM-Large-text2sql-spider model on AI-generated
Spider-format training pairs (JSONL) using HuggingFace Trainer API.

Usage:
    python scripts/fine_tune_t5.py --data data/training_data_validated.jsonl --output-dir models/fine-tuned-t5
    python scripts/fine_tune_t5.py --data data/training_data_validated.jsonl --output-dir models/fine-tuned-t5 --epochs 5 --batch-size 4 --learning-rate 5e-4
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from datasets import Dataset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default hyperparameters
# ---------------------------------------------------------------------------
DEFAULT_MODEL_NAME = "gaussalgo/T5-LM-Large-text2sql-spider"
DEFAULT_LEARNING_RATE = 3e-4
DEFAULT_BATCH_SIZE = 8
DEFAULT_EPOCHS = 10
DEFAULT_MAX_INPUT_LENGTH = 512
DEFAULT_MAX_TARGET_LENGTH = 256


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_data(jsonl_path: str) -> Dict[str, Dataset]:
    """
    Load training pairs from a JSONL file and split 80/20 into train/val.

    Each line in the JSONL must have ``"input"`` and ``"target"`` keys
    (Spider-format text-to-SQL pairs).

    Args:
        jsonl_path: Path to the JSONL file.

    Returns:
        Dict with ``"train"`` and ``"validation"`` HuggingFace Dataset objects.

    Raises:
        FileNotFoundError: If *jsonl_path* does not exist.
        ValueError: If the file contains zero valid pairs.
    """
    path = Path(jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")

    inputs = []
    targets = []

    with path.open("r", encoding="utf-8") as fh:
        for line_num, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                pair = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Line %d: invalid JSON — %s", line_num, exc)
                continue

            if "input" not in pair or "target" not in pair:
                logger.warning("Line %d: missing 'input' or 'target' key", line_num)
                continue

            inputs.append(pair["input"])
            targets.append(pair["target"])

    if not inputs:
        raise ValueError(f"No valid training pairs found in {jsonl_path}")

    dataset = Dataset.from_dict({"input": inputs, "target": targets})

    # 80/20 split with a fixed seed for reproducibility
    split = dataset.train_test_split(test_size=0.2, seed=42)

    logger.info(
        "Loaded %d pairs — train: %d, validation: %d",
        len(dataset),
        len(split["train"]),
        len(split["test"]),
    )

    return {"train": split["train"], "validation": split["test"]}


# ---------------------------------------------------------------------------
# Fine-tuning
# ---------------------------------------------------------------------------
def fine_tune(
    model_name: str,
    train_dataset: Dataset,
    val_dataset: Dataset,
    output_dir: str,
    *,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    batch_size: int = DEFAULT_BATCH_SIZE,
    epochs: int = DEFAULT_EPOCHS,
    max_input_length: int = DEFAULT_MAX_INPUT_LENGTH,
    max_target_length: int = DEFAULT_MAX_TARGET_LENGTH,
    **extra_hparams: Any,
) -> Any:
    """
    Fine-tune a T5 seq2seq model using the HuggingFace Trainer API.

    Loads the base model and tokenizer from *model_name* (HuggingFace hub
    identifier **or** local directory), tokenises the datasets, trains with
    validation-loss evaluation after every epoch, and saves the fine-tuned
    model + tokenizer to *output_dir*.

    Args:
        model_name: HuggingFace model identifier or local path
                    (default: ``gaussalgo/T5-LM-Large-text2sql-spider``).
        train_dataset: HuggingFace ``Dataset`` with ``"input"`` and ``"target"`` columns.
        val_dataset: HuggingFace ``Dataset`` with ``"input"`` and ``"target"`` columns.
        output_dir: Directory to save the fine-tuned model and tokenizer.
        learning_rate: Optimizer learning rate (default ``3e-4``).
        batch_size: Per-device train & eval batch size (default ``8``).
        epochs: Number of training epochs (default ``10``).
        max_input_length: Max tokenised input length (default ``512``).
        max_target_length: Max tokenised target length (default ``256``).
        **extra_hparams: Forwarded to ``TrainingArguments`` for advanced tuning.

    Returns:
        The trained ``transformers.Trainer`` instance.
    """
    from transformers import (
        AutoModelForSeq2SeqLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
    )

    # ------------------------------------------------------------------
    # 1. Load model & tokenizer
    # ------------------------------------------------------------------
    logger.info("Loading model: %s", model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

    # ------------------------------------------------------------------
    # 2. Tokenise datasets
    # ------------------------------------------------------------------
    def _tokenize(examples: Dict) -> Dict:
        model_inputs = tokenizer(
            examples["input"],
            max_length=max_input_length,
            truncation=True,
            padding="max_length",
        )
        labels = tokenizer(
            text_target=examples["target"],
            max_length=max_target_length,
            truncation=True,
            padding="max_length",
        )
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    logger.info("Tokenising training set (%d examples)…", len(train_dataset))
    tokenized_train = train_dataset.map(_tokenize, batched=True, remove_columns=["input", "target"])

    logger.info("Tokenising validation set (%d examples)…", len(val_dataset))
    tokenized_val = val_dataset.map(_tokenize, batched=True, remove_columns=["input", "target"])

    # ------------------------------------------------------------------
    # 3. Training arguments
    # ------------------------------------------------------------------
    training_args = Seq2SeqTrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        predict_with_generate=False,
        save_total_limit=2,
        fp16=False,  # safe default; set True on GPU for speed
        report_to="none",
        **extra_hparams,
    )

    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        model=model,
        padding=True,
    )

    # ------------------------------------------------------------------
    # 4. Train
    # ------------------------------------------------------------------
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_val,
        tokenizer=tokenizer,
        data_collator=data_collator,
    )

    logger.info(
        "Starting training — epochs=%d, batch_size=%d, lr=%s",
        epochs,
        batch_size,
        learning_rate,
    )

    try:
        trainer.train()
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            logger.error(
                "CUDA out of memory. Try reducing --batch-size (current: %d).",
                batch_size,
            )
        raise

    # ------------------------------------------------------------------
    # 5. Save model & tokenizer
    # ------------------------------------------------------------------
    save_path = Path(output_dir) / "final"
    save_path.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(save_path))
    tokenizer.save_pretrained(str(save_path))
    logger.info("Model and tokenizer saved to %s", save_path)

    return trainer


# ---------------------------------------------------------------------------
# Evaluation (Task 6.2)
# ---------------------------------------------------------------------------
def evaluate(model: Any, tokenizer: Any, val_dataset: Dataset) -> Dict:
    """Compute exact-match accuracy, execution accuracy, and avg inference time.

    Iterates over every example in *val_dataset*, generates SQL with the model,
    and computes:
    - **Exact-match accuracy**: fraction where generated SQL == target SQL.
    - **Execution accuracy**: fraction where generated SQL parses as valid SQL
      and is a SELECT-only statement (checked via ``sqlparse``).
    - **Average inference time** per query in milliseconds.

    Logs 10 sample predictions for manual inspection and emits a warning when
    exact-match accuracy falls below 60 %.

    Args:
        model: A ``transformers.AutoModelForSeq2SeqLM`` (or compatible) model.
        tokenizer: The matching ``AutoTokenizer``.
        val_dataset: HuggingFace ``Dataset`` with ``"input"`` and ``"target"`` columns.

    Returns:
        Dict matching the ``EvaluationReport`` schema::

            {
                "total_examples": int,
                "exact_match_accuracy": float,   # 0.0 – 1.0
                "execution_accuracy": float,     # 0.0 – 1.0
                "avg_inference_time_ms": float,
                "sample_predictions": List[Dict], # up to 10 samples
            }
    """
    import sqlparse

    total = len(val_dataset)
    if total == 0:
        logger.warning("Validation dataset is empty — nothing to evaluate.")
        return {
            "total_examples": 0,
            "exact_match_accuracy": 0.0,
            "execution_accuracy": 0.0,
            "avg_inference_time_ms": 0.0,
            "sample_predictions": [],
        }

    exact_matches = 0
    execution_valid = 0
    total_inference_time = 0.0
    sample_predictions: List[Dict] = []

    for idx in range(total):
        input_text = val_dataset[idx]["input"]
        target_sql = val_dataset[idx]["target"]

        # --- Inference with timing -------------------------------------------
        encoded = tokenizer(
            input_text,
            return_tensors="pt",
            max_length=DEFAULT_MAX_INPUT_LENGTH,
            truncation=True,
            padding=True,
        )
        # Move tensors to the same device as the model
        input_ids = encoded.input_ids.to(model.device)
        attention_mask = encoded.attention_mask.to(model.device)

        start = time.time()
        outputs = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_length=DEFAULT_MAX_TARGET_LENGTH,
        )
        elapsed_ms = (time.time() - start) * 1000.0
        total_inference_time += elapsed_ms

        generated_sql = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

        # --- Exact-match check -----------------------------------------------
        if generated_sql == target_sql:
            exact_matches += 1

        # --- Execution accuracy check (valid SQL & SELECT-only) --------------
        try:
            parsed = sqlparse.parse(generated_sql)
            if parsed and len(parsed) > 0:
                stmt = parsed[0]
                stmt_type = stmt.get_type()
                if stmt_type and stmt_type.upper() == "SELECT":
                    execution_valid += 1
        except Exception:
            # Any parse failure → not execution-valid
            pass

        # --- Collect sample predictions (first 10) ---------------------------
        if len(sample_predictions) < 10:
            sample_predictions.append({
                "input": input_text,
                "expected": target_sql,
                "generated": generated_sql,
            })

    # --- Compute metrics -----------------------------------------------------
    exact_match_accuracy = exact_matches / total
    execution_accuracy = execution_valid / total
    avg_inference_time_ms = total_inference_time / total

    # --- Log sample predictions ----------------------------------------------
    logger.info("=" * 60)
    logger.info("Sample predictions (%d / %d):", len(sample_predictions), total)
    logger.info("=" * 60)
    for i, sample in enumerate(sample_predictions, start=1):
        logger.info("  [%d] Input:     %s", i, sample["input"])
        logger.info("  [%d] Expected:  %s", i, sample["expected"])
        logger.info("  [%d] Generated: %s", i, sample["generated"])
        logger.info("-" * 60)

    # --- Summary report ------------------------------------------------------
    logger.info("=" * 60)
    logger.info("Evaluation Summary")
    logger.info("=" * 60)
    logger.info("  Total examples:        %d", total)
    logger.info("  Exact-match accuracy:  %.2f%%", exact_match_accuracy * 100)
    logger.info("  Execution accuracy:    %.2f%%", execution_accuracy * 100)
    logger.info("  Avg inference time:    %.1f ms", avg_inference_time_ms)
    logger.info("=" * 60)

    # --- Low accuracy warning ------------------------------------------------
    if exact_match_accuracy < 0.6:
        logger.warning(
            "Exact-match accuracy (%.2f%%) is below 60%%. "
            "Consider adding more training data or tuning hyperparameters.",
            exact_match_accuracy * 100,
        )

    return {
        "total_examples": total,
        "exact_match_accuracy": exact_match_accuracy,
        "execution_accuracy": execution_accuracy,
        "avg_inference_time_ms": avg_inference_time_ms,
        "sample_predictions": sample_predictions,
    }


# ---------------------------------------------------------------------------
# CLI entry point (Task 6.3)
# ---------------------------------------------------------------------------

def main() -> None:
    """Full pipeline: load → train → evaluate → save → report."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Fine-tune T5-LM-Large-text2sql-spider on Spider-format JSONL training data.",
    )
    parser.add_argument(
        "--data",
        required=True,
        help="Path to the JSONL training data file.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to save the fine-tuned model and tokenizer.",
    )
    parser.add_argument(
        "--model-name",
        default=DEFAULT_MODEL_NAME,
        help=f"HuggingFace model identifier or local path (default: {DEFAULT_MODEL_NAME}).",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=DEFAULT_EPOCHS,
        help=f"Number of training epochs (default: {DEFAULT_EPOCHS}).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Per-device batch size (default: {DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=DEFAULT_LEARNING_RATE,
        help=f"Optimizer learning rate (default: {DEFAULT_LEARNING_RATE}).",
    )

    args = parser.parse_args()

    # --- Configure logging ---------------------------------------------------
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        # --- 1. Load data ----------------------------------------------------
        logger.info("Loading training data from %s", args.data)
        datasets = load_data(args.data)
        logger.info(
            "Data loaded — train: %d, validation: %d",
            len(datasets["train"]),
            len(datasets["validation"]),
        )

        # --- 2. Fine-tune ----------------------------------------------------
        logger.info("Starting fine-tuning with model: %s", args.model_name)
        trainer = fine_tune(
            model_name=args.model_name,
            train_dataset=datasets["train"],
            val_dataset=datasets["validation"],
            output_dir=args.output_dir,
            learning_rate=args.learning_rate,
            batch_size=args.batch_size,
            epochs=args.epochs,
        )

        # --- 3. Evaluate -----------------------------------------------------
        model = trainer.model
        tokenizer = trainer.tokenizer
        logger.info("Evaluating fine-tuned model on validation set…")
        report = evaluate(model, tokenizer, datasets["validation"])

        # --- 4. Print summary ------------------------------------------------
        print("\n" + "=" * 60)
        print("  Fine-Tuning Complete")
        print("=" * 60)
        print(f"  Total validation examples : {report['total_examples']}")
        print(f"  Exact-match accuracy      : {report['exact_match_accuracy']:.2%}")
        print(f"  Execution accuracy        : {report['execution_accuracy']:.2%}")
        print(f"  Avg inference time        : {report['avg_inference_time_ms']:.1f} ms")
        print(f"  Model saved to            : {args.output_dir}/final")
        print("=" * 60 + "\n")

    except FileNotFoundError as exc:
        logger.error("Data file not found: %s", exc)
        sys.exit(1)
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            logger.error(
                "CUDA out of memory during training. "
                "Try reducing --batch-size (current: %d) or use a GPU with more VRAM.",
                args.batch_size,
            )
        else:
            logger.error("Runtime error: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error(
            "Failed to download or load model '%s'. "
            "Check your internet connection and that the model identifier is correct. "
            "Error: %s",
            args.model_name,
            exc,
        )
        sys.exit(1)




if __name__ == "__main__":
    main()
