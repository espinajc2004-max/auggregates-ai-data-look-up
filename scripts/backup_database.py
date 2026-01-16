"""
Database Backup Script
======================
Backs up all important tables from Supabase to JSON files.

Usage:
    python scripts/backup_database.py
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath('.'))

from app.services.supabase_client import get_supabase_client


def backup_table(table_name: str, output_dir: Path, select_columns: str = "*") -> bool:
    """
    Backup a single table to JSON.
    
    Args:
        table_name: Name of the table to backup
        output_dir: Directory to save backup files
        select_columns: Columns to select (default: all)
        
    Returns:
        True if successful, False otherwise
    """
    supabase = get_supabase_client()
    
    try:
        print(f"📦 Backing up {table_name}...", end=" ")
        
        # Fetch all data from table
        data = supabase.get(f"{table_name}?select={select_columns}")
        
        if data is None:
            print(f"⚠️  No data returned")
            return False
        
        # Create output file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f"{table_name}_{timestamp}.json"
        
        # Write to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        file_size = output_file.stat().st_size / 1024  # KB
        print(f"✅ {len(data)} rows ({file_size:.1f} KB)")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Backup all important tables."""
    print("=" * 80)
    print("DATABASE BACKUP SCRIPT")
    print("=" * 80)
    print()
    
    # Create backup directory
    output_dir = Path("backups/data")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Backup directory: {output_dir.absolute()}")
    print()
    
    # Tables to backup
    tables = [
        ("Expenses", "*"),
        ("CashFlow", "*"),
        ("Project", "*"),
        ("Quotation", "*"),
        ("QuotationItem", "*"),
        ("ai_documents", "*"),
        ("Conversation", "*"),
        ("Trip", "*"),
        ("Truck", "*"),
    ]
    
    successful = 0
    failed = 0
    
    for table_name, columns in tables:
        if backup_table(table_name, output_dir, columns):
            successful += 1
        else:
            failed += 1
    
    print()
    print("=" * 80)
    print("BACKUP SUMMARY")
    print("=" * 80)
    print()
    print(f"✅ Successful: {successful}/{len(tables)}")
    print(f"❌ Failed: {failed}/{len(tables)}")
    print()
    
    if successful == len(tables):
        print("🎉 All tables backed up successfully!")
    elif successful > 0:
        print(f"⚠️  {failed} table(s) failed to backup. Check the output above.")
    else:
        print("❌ Backup failed. Check your Supabase connection.")
    
    print()
    print(f"📁 Backup files saved to: {output_dir.absolute()}")
    print()
    
    # Show total backup size
    total_size = sum(f.stat().st_size for f in output_dir.glob("*.json")) / (1024 * 1024)  # MB
    print(f"💾 Total backup size: {total_size:.2f} MB")
    print()


if __name__ == "__main__":
    main()
