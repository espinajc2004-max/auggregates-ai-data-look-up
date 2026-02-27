"""Quick validation of the 5000-pair JSONL dataset."""
import json
import re
from collections import Counter

SPIDER_PREFIX = (
    "tables: ai_documents (id, source_table, file_name, project_name, "
    "searchable_text, metadata, document_type) | query: "
)
VALID_TABLES = ["Expenses", "CashFlow", "Project", "Quotation", "QuotationItem"]
CUSTOM_KEYS = ["Driver", "Supplier", "Remarks", "Method", "Description", "Notes", "Reference"]

errors = []
source_counts = Counter()
intent_counts = Counter()
doc_type_counts = Counter()
features = Counter()
duplicate_targets = Counter()
valid = 0

FILE = "t5_text2sql_5000_pairs.jsonl"

with open(FILE, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            pair = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"Line {i}: Invalid JSON - {e}")
            continue

        inp = pair.get("input", "")
        tgt = pair.get("target", "")

        if "input" not in pair or "target" not in pair:
            errors.append(f"Line {i}: Missing input/target")
            continue

        # Check prefix
        if not inp.startswith(SPIDER_PREFIX):
            errors.append(f"Line {i}: Bad prefix")
            continue

        # Check query not empty
        query = inp[len(SPIDER_PREFIX):].strip()
        if not query:
            errors.append(f"Line {i}: Empty query")
            continue

        # Check SELECT
        tgt_upper = tgt.strip().upper()
        if not tgt_upper.startswith("SELECT"):
            errors.append(f"Line {i}: Not SELECT: {tgt[:60]}")
            continue

        # Check source_table
        found_tables = []
        for t in VALID_TABLES:
            marker = "source_table = '" + t + "'"
            if marker in tgt:
                found_tables.append(t)
                source_counts[t] += 1
        if not found_tables:
            errors.append(f"Line {i}: No source_table filter")
            continue

        # Check document_type
        if "document_type = 'file'" in tgt:
            doc_type_counts["file"] += 1
        elif "document_type = 'row'" in tgt:
            doc_type_counts["row"] += 1
        else:
            errors.append(f"Line {i}: No document_type filter")
            continue

        # Track SQL features
        if "metadata->>" in tgt:
            features["metadata_access"] += 1
        if "ILIKE" in tgt_upper:
            features["ilike"] += 1
        if "::numeric" in tgt.lower():
            features["numeric_cast"] += 1
        if "GROUP BY" in tgt_upper:
            features["group_by"] += 1
        if "ORDER BY" in tgt_upper:
            features["order_by"] += 1
        if "LIMIT" in tgt_upper:
            features["limit"] += 1
        if "UNION" in tgt_upper:
            features["union"] += 1
        if tgt_upper.count("SELECT") > 1:
            features["subquery"] += 1
        if "IS NULL" in tgt_upper or "IS NOT NULL" in tgt_upper:
            features["null_check"] += 1
        if "HAVING" in tgt_upper:
            features["having"] += 1
        if "BETWEEN" in tgt_upper:
            features["between"] += 1

        # Custom keys
        for ck in CUSTOM_KEYS:
            if "metadata->>'" + ck + "'" in tgt:
                features["custom_keys"] += 1
                break

        # Intent detection
        if "SUM(" in tgt_upper:
            intent_counts["sum"] += 1
        elif "AVG(" in tgt_upper:
            intent_counts["average"] += 1
        elif "COUNT(" in tgt_upper:
            intent_counts["count"] += 1
        elif "DISTINCT" in tgt_upper:
            intent_counts["list_categories"] += 1
        elif "document_type = 'file'" in tgt:
            intent_counts["list_files"] += 1
        elif "GROUP BY" in tgt_upper:
            intent_counts["compare"] += 1
        else:
            intent_counts["query_data"] += 1

        # Track duplicates
        normalized = re.sub(r"\s+", " ", tgt.strip().lower())
        duplicate_targets[normalized] += 1

        valid += 1


# --- Check metadata key coverage ---
all_keys_found = Counter()
key_patterns = [
    "Category", "Expenses", "Name",  # Expenses
    "Type", "Amount",  # CashFlow (Category shared)
    "project_name", "client_name", "location", "status",  # Project
    "quote_number", "total_amount",  # Quotation (status, project_name shared)
    "plate_no", "dr_no", "material", "quarry_location", "truck_type", "volume", "line_total",  # QuotationItem
]

with open(FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            pair = json.loads(line)
        except Exception:
            continue
        tgt = pair.get("target", "")
        for k in key_patterns:
            if "metadata->>'" + k + "'" in tgt:
                all_keys_found[k] += 1

# --- Sample first/last pairs ---
samples_first = []
samples_last = []
with open(FILE, "r", encoding="utf-8") as f:
    all_lines = f.readlines()
    for line in all_lines[:3]:
        try:
            samples_first.append(json.loads(line.strip()))
        except Exception:
            pass
    for line in all_lines[-3:]:
        try:
            samples_last.append(json.loads(line.strip()))
        except Exception:
            pass

# --- Report ---
exact_dupes = sum(1 for c in duplicate_targets.values() if c > 1)
total_dupe_lines = sum(c - 1 for c in duplicate_targets.values() if c > 1)

print("=" * 65)
print("  DATASET VALIDATION: t5_text2sql_5000_pairs.jsonl")
print("=" * 65)
print(f"  Total lines:     5000")
print(f"  Valid pairs:     {valid}")
print(f"  Errors:          {len(errors)}")
print(f"  Error rate:      {len(errors)/50:.1f}%")
print()

print("--- Source Table Distribution ---")
for t in sorted(source_counts, key=source_counts.get, reverse=True):
    pct = source_counts[t] / max(valid, 1) * 100
    bar = "#" * int(pct / 2)
    print(f"  {t:20s} {source_counts[t]:5d} ({pct:5.1f}%) {bar}")
print()

print("--- Intent Distribution ---")
for intent in sorted(intent_counts, key=intent_counts.get, reverse=True):
    pct = intent_counts[intent] / max(valid, 1) * 100
    bar = "#" * int(pct / 2)
    print(f"  {intent:20s} {intent_counts[intent]:5d} ({pct:5.1f}%) {bar}")
print()

print("--- Document Type ---")
for dt in sorted(doc_type_counts, key=doc_type_counts.get, reverse=True):
    print(f"  {dt:20s} {doc_type_counts[dt]:5d}")
print()

print("--- SQL Features ---")
for feat in sorted(features, key=features.get, reverse=True):
    print(f"  {feat:20s} {features[feat]:5d}")
print()

print("--- Metadata Key Coverage ---")
missing_keys = []
for k in key_patterns:
    count = all_keys_found.get(k, 0)
    status = "OK" if count > 0 else "MISSING"
    if count == 0:
        missing_keys.append(k)
    print(f"  {k:20s} {count:5d}  {status}")
print()

print("--- Duplicates ---")
print(f"  Unique SQL targets:  {len(duplicate_targets)}")
print(f"  Duplicate groups:    {exact_dupes}")
print(f"  Total dupe lines:    {total_dupe_lines}")
print(f"  Uniqueness rate:     {len(duplicate_targets)/max(valid,1)*100:.1f}%")
print()

if errors:
    print(f"--- First 20 Errors (of {len(errors)}) ---")
    for e in errors[:20]:
        print(f"  {e}")
    print()

print("--- Sample Pairs (first 3) ---")
for s in samples_first:
    q = s["input"].split("query: ")[-1]
    print(f"  Q: {q[:80]}")
    print(f"  S: {s['target'][:100]}")
    print()

print("--- Sample Pairs (last 3) ---")
for s in samples_last:
    q = s["input"].split("query: ")[-1]
    print(f"  Q: {q[:80]}")
    print(f"  S: {s['target'][:100]}")
    print()

# --- Verdict ---
print("=" * 65)
issues = []
if len(errors) > valid * 0.05:
    issues.append(f"High error rate: {len(errors)/50:.1f}%")
if missing_keys:
    issues.append(f"Missing metadata keys: {', '.join(missing_keys)}")
if total_dupe_lines > valid * 0.1:
    issues.append(f"Too many duplicates: {total_dupe_lines}")
if valid < 4500:
    issues.append(f"Low valid count: {valid} (expected ~5000)")

# Check source table balance
for t in VALID_TABLES:
    pct = source_counts.get(t, 0) / max(valid, 1) * 100
    if pct < 3:
        issues.append(f"Low coverage for {t}: {pct:.1f}%")

if not issues:
    print("  VERDICT: PASS - Dataset looks good for training!")
else:
    print("  VERDICT: ISSUES FOUND")
    for issue in issues:
        print(f"    - {issue}")
print("=" * 65)
