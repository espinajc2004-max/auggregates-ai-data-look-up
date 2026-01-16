"""
Add Phase 2 Test Data
=====================
Adds diverse, realistic test data for comprehensive Phase 2 testing.

Scenarios:
1. Multiple projects with different expense patterns
2. Date range queries (last month, this year)
3. Complex aggregations (by project, by category, by date)
4. CashFlow data for RBAC testing
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
import random

# Test data to insert
test_data = []

# Project names
projects = ["Skyline Tower", "Green Valley Homes", "Metro Plaza"]

# Expense categories
expense_categories = ["labor", "materials", "equipment", "fuel", "utilities", "permits", "insurance"]

# Generate expenses for last 3 months
today = datetime.now()
for i in range(30):  # 30 expense records
    days_ago = random.randint(0, 90)
    date = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    project = random.choice(projects)
    category = random.choice(expense_categories)
    amount = random.randint(500, 5000)
    
    test_data.append({
        "source_table": "Expenses",
        "file_name": f"expenses_{date}.xlsx",
        "project_name": project,
        "metadata": {
            "Date": date,
            "Name": f"{category}_{i+1}",
            "Category": category,
            "Expenses": str(amount),
            "Description": f"{category.title()} expense for {project}"
        }
    })

# Generate CashFlow data (for RBAC testing)
cashflow_types = ["inflow", "outflow"]
for i in range(15):  # 15 cashflow records
    days_ago = random.randint(0, 90)
    date = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    project = random.choice(projects)
    cf_type = random.choice(cashflow_types)
    amount = random.randint(10000, 50000)
    
    test_data.append({
        "source_table": "CashFlow",
        "file_name": f"cashflow_{date}.xlsx",
        "project_name": project,
        "metadata": {
            "Date": date,
            "Type": cf_type,
            "Amount": str(amount),
            "product": f"Payment for {project}",
            "Description": f"{cf_type.title()} for {project}"
        }
    })

# Print SQL INSERT statements
print("-- Phase 2 Test Data")
print("-- Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print()

for i, record in enumerate(test_data, 1):
    metadata_json = str(record['metadata']).replace("'", "''")
    
    sql = f"""INSERT INTO ai_documents (source_table, file_name, project_name, metadata, content, search_vector)
VALUES (
    '{record['source_table']}',
    '{record['file_name']}',
    '{record['project_name']}',
    '{metadata_json}'::jsonb,
    '{record['metadata'].get('Description', '')}',
    to_tsvector('english', '{record['metadata'].get('Description', '')}')
);"""
    
    print(sql)
    print()

print(f"-- Total records: {len(test_data)}")
print(f"-- Expenses: {sum(1 for r in test_data if r['source_table'] == 'Expenses')}")
print(f"-- CashFlow: {sum(1 for r in test_data if r['source_table'] == 'CashFlow')}")
