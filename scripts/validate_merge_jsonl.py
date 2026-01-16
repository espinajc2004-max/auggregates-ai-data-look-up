\
"""
JSONL Validation + Merge Script
Validates and merges multiple JSONL dataset files for AI training.

Usage:
    # Validate a single file
    python scripts/validate_merge_jsonl.py validate stage2_t5_text2sql_part-001.jsonl
    
    # Merge multiple files
    python scripts/validate_merge_jsonl.py merge t5_train.jsonl stage2_t5_text2sql_part-*.jsonl
"""

import json
import sys
from pathlib import Path
from typing import List
import glob


def validate_jsonl(path: str) -> tuple[int, int]:
    """
    Validate JSONL file format.
    
    Args:
        path: Path to JSONL file
        
    Returns:
        Tuple of (total_lines, bad_lines)
    """
    p = Path(path)
    
    if not p.exists():
        print(f"❌ File not found: {path}")
        return 0, 0
    
    bad = 0
    total = 0
    
    print(f"\n🔍 Validating: {p.name}")
    print("-" * 60)
    
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        total += 1
        line = line.strip()
        
        if not line:
            continue
            
        try:
            json.loads(line)
        except Exception as e:
            bad += 1
            print(f"[BAD] Line {i}: {str(e)}")
            print(f"      Content: {line[:120]}...")
    
    print("-" * 60)
    if bad == 0:
        print(f"✅ {p.name}: total={total}, bad={bad} (ALL VALID)")
    else:
        print(f"❌ {p.name}: total={total}, bad={bad} (ERRORS FOUND)")
    
    return total, bad


def merge_jsonl(out_path: str, *inputs: str) -> int:
    """
    Merge multiple JSONL files into one.
    
    Args:
        out_path: Output file path
        *inputs: Input file paths (can use wildcards)
        
    Returns:
        Total lines merged
    """
    out = Path(out_path)
    total_lines = 0
    
    # Expand wildcards
    all_files = []
    for pattern in inputs:
        if '*' in pattern:
            all_files.extend(glob.glob(pattern))
        else:
            all_files.append(pattern)
    
    if not all_files:
        print("❌ No input files found!")
        return 0
    
    print(f"\n📦 Merging {len(all_files)} files into: {out.name}")
    print("-" * 60)
    
    with out.open("w", encoding="utf-8") as w:
        for inp in all_files:
            inp_path = Path(inp)
            
            if not inp_path.exists():
                print(f"⚠️  Skipping (not found): {inp}")
                continue
            
            lines_added = 0
            for line in inp_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    w.write(line + "\n")
                    lines_added += 1
                    total_lines += 1
            
            print(f"✅ {inp_path.name}: {lines_added} lines")
    
    print("-" * 60)
    print(f"✅ Merged {total_lines} total lines → {out.name}")
    
    return total_lines


def validate_all_stages():
    """Validate all stage datasets."""
    print("\n" + "=" * 60)
    print("🔍 VALIDATING ALL STAGE DATASETS")
    print("=" * 60)
    
    data_dir = Path("ml/training/data")
    
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        return
    
    # Find all JSONL files
    jsonl_files = list(data_dir.glob("*.jsonl"))
    
    if not jsonl_files:
        print(f"⚠️  No JSONL files found in {data_dir}")
        return
    
    total_files = 0
    total_bad = 0
    
    for file in sorted(jsonl_files):
        total, bad = validate_jsonl(str(file))
        total_files += 1
        total_bad += bad
    
    print("\n" + "=" * 60)
    print(f"📊 SUMMARY: {total_files} files validated")
    if total_bad == 0:
        print("✅ ALL FILES VALID!")
    else:
        print(f"❌ {total_bad} total errors found")
    print("=" * 60)


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCommands:")
        print("  validate <file>           - Validate a single JSONL file")
        print("  validate-all              - Validate all files in ml/training/data/")
        print("  merge <output> <inputs>   - Merge multiple JSONL files")
        print("\nExamples:")
        print("  python scripts/validate_merge_jsonl.py validate ml/training/data/t5_train.jsonl")
        print("  python scripts/validate_merge_jsonl.py validate-all")
        print("  python scripts/validate_merge_jsonl.py merge t5_all.jsonl stage2_t5_*.jsonl")
        return
    
    command = sys.argv[1]
    
    if command == "validate":
        if len(sys.argv) < 3:
            print("❌ Usage: validate <file>")
            return
        
        file_path = sys.argv[2]
        validate_jsonl(file_path)
    
    elif command == "validate-all":
        validate_all_stages()
    
    elif command == "merge":
        if len(sys.argv) < 4:
            print("❌ Usage: m