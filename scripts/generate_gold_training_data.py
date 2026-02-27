"""
Gold Training Data Generator for AU-Ggregates AI T5 Text-to-SQL
================================================================
Generates high-quality, schema-verified training pairs for fine-tuning
T5-LM-Large-text2sql-spider.

Unlike the AI-generated 5000 pairs, this script:
1. Uses the REAL ai_documents schema as ground truth
2. Generates diverse, natural English questions (not templated)
3. Every SQL is structurally validated against the schema
4. Covers all 5 source tables, all metadata keys, all intent types
5. Includes realistic Filipino construction industry entity values
6. Produces Spider-format JSONL compatible with T5 fine-tuning

Schema Reference (from SchemaRegistry GLOBAL_SCHEMA):
  ai_documents columns: id, source_table, file_name, project_name,
                         searchable_text, metadata (JSONB), document_type

  Expenses:      Category, Expenses, Name
  CashFlow:      Type, Amount, Category
  Project:       project_name, client_name, location, status
  Quotation:     quote_number, status, total_amount, project_name
  QuotationItem: plate_no, dr_no, material, quarry_location,
                 truck_type, volume, line_total

  Numeric keys (need ::numeric cast): Expenses, Amount, total_amount,
                                       volume, line_total

Usage:
    python scripts/generate_gold_training_data.py
    python scripts/generate_gold_training_data.py --output data/gold_training.jsonl --count 2000
    python scripts/generate_gold_training_data.py --validate-only data/gold_training.jsonl
"""

import json
import random
import argparse
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# ============================================================================
# SPIDER FORMAT PREFIX (must match phi3_service.py SPIDER_SCHEMA exactly)
# ============================================================================
SPIDER_PREFIX = (
    "tables: ai_documents ("
    "id, source_table, file_name, project_name, "
    "searchable_text, metadata, document_type"
    ") | query: "
)

# ============================================================================
# SCHEMA DEFINITION — single source of truth
# ============================================================================
SCHEMA = {
    "table": "ai_documents",
    "columns": ["id", "source_table", "file_name", "project_name",
                 "searchable_text", "metadata", "document_type"],
    "source_tables": {
        "Expenses": {
            "metadata_keys": ["Category", "Expenses", "Name"],
            "numeric_keys": ["Expenses"],
        },
        "CashFlow": {
            "metadata_keys": ["Type", "Amount", "Category"],
            "numeric_keys": ["Amount"],
        },
        "Project": {
            "metadata_keys": ["project_name", "client_name", "location", "status"],
            "numeric_keys": [],
        },
        "Quotation": {
            "metadata_keys": ["quote_number", "status", "total_amount", "project_name"],
            "numeric_keys": ["total_amount"],
        },
        "QuotationItem": {
            "metadata_keys": ["plate_no", "dr_no", "material", "quarry_location",
                              "truck_type", "volume", "line_total"],
            "numeric_keys": ["volume", "line_total"],
        },
    },
    "document_types": ["file", "row"],
}

# ============================================================================
# REALISTIC ENTITY VALUES — Filipino construction industry
# ============================================================================

# Expense categories (real construction industry)
EXPENSE_CATEGORIES = [
    "Fuel", "Labor", "Materials", "Equipment", "Food", "Transportation",
    "Office Supplies", "Cement", "Steel", "Sand", "Gravel", "Paint",
    "Electrical", "Plumbing", "Rental", "Safety Gear", "Tools",
    "Lumber", "Roofing", "Concrete", "Welding", "Hauling",
]

# CashFlow types
CASHFLOW_TYPES = ["Income", "Expense", "Transfer", "Loan", "Payment",
                  "Refund", "Advance", "Disbursement"]

# CashFlow categories
CASHFLOW_CATEGORIES = [
    "Client Payment", "Material Purchase", "Salary", "Loan Disbursement",
    "Equipment Rental", "Subcontractor Payment", "Tax Payment",
    "Insurance", "Utility Bills", "Fuel Advance", "Petty Cash",
]

# Project names (realistic Filipino construction)
PROJECT_NAMES = [
    "SJDM Residences", "Francis Gays", "Manila Tower Phase 2",
    "Highway 5 Extension", "Building C Phase 2", "BGC Tower",
    "Quezon City Mall", "Makati Office", "Taguig Hub",
    "Cavite Housing Phase 1", "Laguna Logistics Park",
    "Bulacan Bypass Road", "Cebu Business Center",
    "Davao Depot Upgrade", "Iloilo Port Expansion",
    "Clark Green City", "Batangas Industrial Zone",
    "Pampanga Flood Control", "Rizal Provincial Road",
    "Alabang Complex", "Pasig Riverside",
]

# Client names
CLIENT_NAMES = [
    "DPWH", "Ayala Corp", "SM Prime Holdings", "Megaworld",
    "STI Construction", "ABC Corp", "XYZ Builders",
    "Metro Contractors", "JG Summit", "San Miguel Corp",
    "Filinvest", "DMCI Holdings", "First Balfour",
    "EEI Corporation", "Leighton Contractors",
]

# Locations
LOCATIONS = [
    "Quezon City", "Makati", "Taguig", "Manila", "Pasig",
    "Cebu City", "Davao City", "Iloilo City", "Cavite",
    "Laguna", "Bulacan", "Pampanga", "Batangas", "Rizal",
    "Clark", "Subic", "Alabang", "BGC", "Ortigas",
]

# Project statuses
PROJECT_STATUSES = ["Active", "Completed", "On Hold", "Cancelled", "Pending"]

# Quotation statuses
QUOTATION_STATUSES = ["Draft", "Sent", "Approved", "Rejected", "Expired"]

# File names (realistic)
FILE_NAMES = [
    "francis gays", "jc", "jash gay", "main expenses",
    "Q1 report", "site A costs", "monthly summary",
    "january expenses", "february cashflow", "march report",
    "fuel log", "labor costs", "material purchases",
    "equipment rental", "petty cash", "payroll",
    "project alpha expenses", "site B materials",
]

# Person names (Filipino)
PERSON_NAMES = [
    "Juan Dela Cruz", "Maria Santos", "Pedro Cruz",
    "Jose Reyes", "Ana Garcia", "Carlos Mendoza",
    "Rosa Fernandez", "Miguel Torres", "Elena Ramos",
    "Roberto Villanueva", "Carmen Lopez", "Antonio Bautista",
    "Liza Aquino", "Ramon Gonzales", "Sofia Castillo",
]

# Materials (QuotationItem)
MATERIALS = [
    "Gravel", "Sand", "Washed Sand", "Crushed Rock",
    "Fill Material", "Boulders", "Limestone", "Aggregate",
    "Base Course", "Sub-base", "Riprap", "Armour Rock",
]

# Quarry locations
QUARRY_LOCATIONS = [
    "Montalban", "Teresa", "Angono", "San Mateo",
    "Rodriguez", "Tanay", "Antipolo", "Binangonan",
]

# Plate numbers
PLATE_NUMBERS = [
    "ABC-1234", "XYZ-5678", "DEF-9012", "GHI-3456",
    "JKL-7890", "MNO-2345", "PQR-6789", "STU-0123",
    "VWX-4567", "YZA-8901", "BCD-2345", "EFG-6789",
]

# DR numbers
DR_NUMBERS = [
    "DR-001", "DR-002", "DR-003", "DR-004", "DR-005",
    "DR-2026-0042", "DR-1234", "DR-5001", "DR-100",
    "DR-2026-0100", "DR-2026-0200", "DR-2026-0300",
]

# Truck types
TRUCK_TYPES = ["6-Wheeler", "10-Wheeler", "Dump Truck", "Trailer",
               "Mini Dump", "Flatbed", "Mixer Truck"]

# Quote numbers
QUOTE_NUMBERS = [
    "QT-2026-001", "QT-2026-002", "QT-2026-003",
    "QT-0042", "Q-1234", "QT-2026-100", "QT-2026-200",
    "QUO-2026-0001", "QUO-2026-0002", "QUO-2026-0003",
]

# Custom/dynamic metadata keys (5-10% of pairs should use these)
CUSTOM_KEYS = [
    "Driver", "Supplier", "Remarks", "Method", "Description",
    "Reference", "Receipt No", "Voucher", "Approved By",
]

# Numeric thresholds for comparison queries
THRESHOLDS = [500, 1000, 2500, 5000, 10000, 15000, 25000, 50000, 100000]

# ============================================================================
# QUESTION TEMPLATES — diverse natural English phrasing
# Each template is a (question_template, sql_template, intent_type) tuple
# Placeholders: {cat}, {file}, {project}, {name}, {amount}, {source_table}, etc.
# ============================================================================

