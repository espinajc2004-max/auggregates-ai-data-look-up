# T5 Training Data Generation Prompt

## Purpose

Use this prompt with an external AI (ChatGPT, Claude, etc.) to generate exactly 5,000 diverse English training pairs for fine-tuning the T5-LM-Large-text2sql-spider model. The model translates natural language questions into SQL queries against our `ai_documents` table.

Copy everything below the line into the AI chat.

---

## PROMPT START

You are a training data generator for a text-to-SQL model. Generate exactly 5,000 diverse English training pairs in JSONL format. Each pair maps a natural language question to a SQL query against a PostgreSQL database.

### Database Schema

The database has a single table:

```sql
CREATE TABLE ai_documents (
    id UUID PRIMARY KEY,
    source_table TEXT NOT NULL,        -- 'Expenses', 'CashFlow', 'Project', 'Quotation', or 'QuotationItem'
    file_name TEXT,                     -- name of the uploaded file
    project_name TEXT,                  -- name of the project
    searchable_text TEXT NOT NULL,      -- full-text search content
    metadata JSONB DEFAULT '{}',        -- structured data (see keys below)
    document_type TEXT DEFAULT 'row'    -- 'file' for file-level docs, 'row' for data rows
);
```

### Metadata JSONB Keys

The `metadata` column is a JSONB object. The keys depend on `source_table`.

These are the standard (GLOBAL) metadata keys per source table. Individual files may also contain additional CUSTOM metadata keys created by users (e.g., "Driver", "Remarks", "Supplier"). The model should handle any key name using `metadata->>'KeyName'` syntax.

**Expenses metadata keys:**
| Key | Description | Example Values |
|-----|-------------|----------------|
| Category | Expense category | "Fuel", "Labor", "Materials", "Equipment", "Food", "Transportation", "Office Supplies" |
| Expenses | Monetary amount (text) | "1500.00", "250.50", "10000" |
| Name | Person/entity name | "John Doe", "Maria Santos", "Pedro Cruz" |

**CashFlow metadata keys:**
| Key | Description | Example Values |
|-----|-------------|----------------|
| Type | Transaction type | "Income", "Expense", "Transfer", "Loan", "Payment" |
| Amount | Monetary amount (text) | "50000.00", "12500", "8750.50" |
| Category | Cash flow category | "Client Payment", "Material Purchase", "Salary", "Loan Disbursement" |

**Project metadata keys:**
| Key | Description | Example Values |
|-----|-------------|----------------|
| project_name | Name of the project | "Manila Tower", "Highway 5 Extension", "Building C Phase 2" |
| client_name | Client or company name | "DPWH", "Ayala Corp", "SM Prime Holdings" |
| location | Project location | "Quezon City", "Taguig", "Cebu" |
| status | Project status | "Active", "Completed", "On Hold", "Cancelled" |

**Quotation metadata keys:**
| Key | Description | Example Values |
|-----|-------------|----------------|
| quote_number | Quotation reference number | "QT-2026-001", "QT-0042", "Q-1234" |
| status | Quotation status | "Draft", "Sent", "Approved", "Rejected", "Expired" |
| total_amount | Total quotation amount (text) | "150000.00", "2500000", "87500.50" |
| project_name | Associated project name | "Manila Tower", "Highway 5 Extension" |

**QuotationItem metadata keys (delivery/line items):**
| Key | Description | Example Values |
|-----|-------------|----------------|
| plate_no | Vehicle plate number | "ABC-1234", "XYZ-5678", "DEF-9012" |
| dr_no | Delivery receipt number | "DR-001", "DR-2026-0042", "DR-1234" |
| material | Material type | "Gravel", "Sand", "Crushed Rock", "Fill Material", "Boulders" |
| quarry_location | Source quarry location | "Montalban", "Teresa", "Angono", "San Mateo" |
| truck_type | Type of truck used | "10-Wheeler", "6-Wheeler", "Dump Truck", "Trailer" |
| volume | Volume delivered (text) | "12.5", "8.0", "15.75" |
| line_total | Line item total amount (text) | "25000.00", "18750", "31500.50" |

> **Note on CUSTOM dynamic metadata keys:** Users can add custom columns to their Expenses and CashFlow files (e.g., "Driver", "Supplier", "Remarks", "Method", "Description"). These become additional metadata keys in `ai_documents` alongside the standard keys listed above. The model should be able to handle any metadata key name using `metadata->>'KeyName'` syntax, not just the standard keys. When generating training data, focus on the standard keys above but include a small percentage (5–10%) of pairs that demonstrate querying arbitrary/custom key names.

### Spider Input Format

The T5 model expects input in Spider format:

```
tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: <natural_language_question>
```

The schema prefix is always exactly:
```
tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: 
```

### Intent Types to Cover

Generate training pairs for ALL of these intent types. Distribute pairs roughly evenly, with slight emphasis on the more common types (query_data, sum, count):

1. **list_files** — List available files/documents
2. **query_data** — Retrieve specific rows or data
3. **sum** — Sum monetary values (Expenses, Amount, total_amount, volume, line_total)
4. **count** — Count rows matching criteria
5. **average** — Average monetary values
6. **compare** — Compare values across files, projects, or categories
7. **list_categories** — List distinct values of a metadata column
8. **date_filter** — Filter data by date or date range

### SQL Rules (CRITICAL — follow these exactly)

1. **Always include `source_table` filter**: Every query must filter by `source_table = 'Expenses'`, `source_table = 'CashFlow'`, `source_table = 'Project'`, `source_table = 'Quotation'`, or `source_table = 'QuotationItem'` (or combine with UNION if the question spans multiple tables).

2. **Always include `document_type` filter**:
   - For `list_files` intent: use `document_type = 'file'`
   - For all data queries (query_data, sum, count, average, compare, list_categories, date_filter): use `document_type = 'row'`

3. **Use JSONB access patterns for metadata columns**: Access metadata values using `metadata->>'ColumnName'` (double arrow for text extraction). Examples:
   - `metadata->>'Category'`
   - `metadata->>'Expenses'`
   - `metadata->>'Amount'`
   - `metadata->>'Type'`
   - `metadata->>'project_name'`
   - `metadata->>'total_amount'`
   - `metadata->>'volume'`

4. **Cast numeric values for aggregation**: When summing or averaging, cast to numeric. The numeric metadata keys are: `Expenses`, `Amount`, `total_amount`, `volume`, `line_total`. Examples:
   - `SUM((metadata->>'Expenses')::numeric)`
   - `AVG((metadata->>'Amount')::numeric)`
   - `SUM((metadata->>'total_amount')::numeric)`
   - `SUM((metadata->>'volume')::numeric)`
   - `SUM((metadata->>'line_total')::numeric)`

5. **Use ILIKE for text matching**: For category, name, material, status, and other text filters:
   - `metadata->>'Category' ILIKE '%fuel%'`
   - `metadata->>'Name' ILIKE '%john%'`
   - `metadata->>'material' ILIKE '%gravel%'`
   - `metadata->>'status' ILIKE '%active%'`

6. **SELECT only**: Every target SQL must be a SELECT statement. Never generate INSERT, UPDATE, DELETE, DROP, or any write operation.

7. **Reference only `ai_documents`**: Never reference any other table.

8. **Use standard column references for non-metadata columns**: `file_name`, `project_name`, `source_table`, `document_type` are regular columns, not inside metadata.

### Filter Combinations

Generate pairs using these filters individually AND in combination:

- **file_name** filter: `file_name ILIKE '%...'`
- **project_name** filter: `project_name ILIKE '%...'`
- **category** filter: `metadata->>'Category' ILIKE '%...'`
- **name** filter: `metadata->>'Name' ILIKE '%...'`
- **type** filter (CashFlow): `metadata->>'Type' ILIKE '%...'`
- **status** filter (Project/Quotation): `metadata->>'status' ILIKE '%...'`
- **material** filter (QuotationItem): `metadata->>'material' ILIKE '%...'`
- **plate_no** filter (QuotationItem): `metadata->>'plate_no' ILIKE '%...'`
- **dr_no** filter (QuotationItem): `metadata->>'dr_no' ILIKE '%...'`
- **client_name** filter (Project): `metadata->>'client_name' ILIKE '%...'`
- **quote_number** filter (Quotation): `metadata->>'quote_number' ILIKE '%...'`
- **quarry_location** filter (QuotationItem): `metadata->>'quarry_location' ILIKE '%...'`
- **truck_type** filter (QuotationItem): `metadata->>'truck_type' ILIKE '%...'`

Combined filter examples:
- file_name + category
- project_name + status
- category + name
- file_name + project_name + category
- material + quarry_location
- plate_no + dr_no
- quote_number + project_name
- client_name + status
- truck_type + material + quarry_location
- No extra filters (just source_table + document_type)

### Output Format

Output one JSON object per line (JSONL format). Each object has exactly two keys:

```json
{"input": "tables: ai_documents (...) | query: <question>", "target": "SELECT ...;"}
```

Do NOT wrap the output in a code block. Output raw JSONL lines only.

### Diversity Guidelines

- **Vary phrasing**: Use different ways to ask the same type of question. Examples for sum: "total expenses", "how much was spent", "what's the sum of", "add up all", "give me the total", "calculate total cost"
- **Vary entity names**: Use diverse file names (e.g., "main expenses", "Q1 report", "site A costs", "manila tower"), project names (e.g., "Project Alpha", "Highway 5", "Building C", "Phase 2"), material names, quarry locations, plate numbers
- **Vary column usage**: Mix metadata keys across all 5 source tables:
  - Expenses: Category, Expenses, Name
  - CashFlow: Type, Amount, Category
  - Project: project_name, client_name, location, status
  - Quotation: quote_number, status, total_amount, project_name
  - QuotationItem: plate_no, dr_no, material, quarry_location, truck_type, volume, line_total
- **Vary filter combinations**: Some queries with no filters beyond source_table, some with one filter, some with two, some with three or more
- **Vary SQL structure**: Use different SELECT columns, different WHERE clause orderings, different aggregation patterns
- **Avoid repetitive patterns**: Each pair should be meaningfully different from every other pair. Don't just swap one word — change the sentence structure, the filters, the columns, and the intent
- **Mix source tables**: Roughly 35% Expenses, 25% CashFlow, 15% Project, 15% Quotation, 10% QuotationItem queries
- **Include edge cases**: Queries with no filters, queries with many filters, queries asking about specific statuses, specific materials, specific plate numbers, cross-project comparisons

### Example Training Pairs

Here are 25 example pairs demonstrating the expected format and variety across all 5 source tables. Your generated pairs should follow this pattern but be much more diverse:

```jsonl
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: show all expense files", "target": "SELECT id, file_name, project_name FROM ai_documents WHERE source_table = 'Expenses' AND document_type = 'file';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: what are the total fuel expenses", "target": "SELECT SUM((metadata->>'Expenses')::numeric) AS total FROM ai_documents WHERE source_table = 'Expenses' AND metadata->>'Category' ILIKE '%fuel%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: how many labor entries are in project alpha", "target": "SELECT COUNT(*) AS count FROM ai_documents WHERE source_table = 'Expenses' AND metadata->>'Category' ILIKE '%labor%' AND project_name ILIKE '%alpha%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: list all categories in the main expenses file", "target": "SELECT DISTINCT metadata->>'Category' AS category FROM ai_documents WHERE source_table = 'Expenses' AND file_name ILIKE '%main expenses%' AND document_type = 'row' ORDER BY category;"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: show expenses by john doe", "target": "SELECT metadata->>'Category' AS category, metadata->>'Expenses' AS amount, metadata->>'Name' AS name FROM ai_documents WHERE source_table = 'Expenses' AND metadata->>'Name' ILIKE '%john doe%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: compare fuel costs between manila tower and building c", "target": "SELECT project_name, SUM((metadata->>'Expenses')::numeric) AS total FROM ai_documents WHERE source_table = 'Expenses' AND metadata->>'Category' ILIKE '%fuel%' AND project_name IN ('manila tower', 'building c') AND document_type = 'row' GROUP BY project_name;"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: average expense amount for materials", "target": "SELECT AVG((metadata->>'Expenses')::numeric) AS average FROM ai_documents WHERE source_table = 'Expenses' AND metadata->>'Category' ILIKE '%materials%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: list all cashflow files", "target": "SELECT id, file_name, project_name FROM ai_documents WHERE source_table = 'CashFlow' AND document_type = 'file';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: total cash flow amount for project highway 5", "target": "SELECT SUM((metadata->>'Amount')::numeric) AS total_amount FROM ai_documents WHERE source_table = 'CashFlow' AND project_name ILIKE '%highway 5%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: how many cashflow entries have amount greater than 10000", "target": "SELECT COUNT(*) AS count FROM ai_documents WHERE source_table = 'CashFlow' AND (metadata->>'Amount')::numeric > 10000 AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: show all income type cashflow entries", "target": "SELECT metadata->>'Type' AS type, metadata->>'Amount' AS amount, metadata->>'Category' AS category FROM ai_documents WHERE source_table = 'CashFlow' AND metadata->>'Type' ILIKE '%income%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: average cashflow amount by category", "target": "SELECT metadata->>'Category' AS category, AVG((metadata->>'Amount')::numeric) AS avg_amount FROM ai_documents WHERE source_table = 'CashFlow' AND document_type = 'row' GROUP BY category;"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: list all projects", "target": "SELECT metadata->>'project_name' AS project_name, metadata->>'client_name' AS client_name, metadata->>'location' AS location, metadata->>'status' AS status FROM ai_documents WHERE source_table = 'Project' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: show active projects", "target": "SELECT metadata->>'project_name' AS project_name, metadata->>'client_name' AS client_name, metadata->>'location' AS location FROM ai_documents WHERE source_table = 'Project' AND metadata->>'status' ILIKE '%active%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: how many projects does DPWH have", "target": "SELECT COUNT(*) AS count FROM ai_documents WHERE source_table = 'Project' AND metadata->>'client_name' ILIKE '%DPWH%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: list projects in quezon city", "target": "SELECT metadata->>'project_name' AS project_name, metadata->>'client_name' AS client_name, metadata->>'status' AS status FROM ai_documents WHERE source_table = 'Project' AND metadata->>'location' ILIKE '%quezon city%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: total amount of all quotations", "target": "SELECT SUM((metadata->>'total_amount')::numeric) AS total FROM ai_documents WHERE source_table = 'Quotation' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: show approved quotations for manila tower", "target": "SELECT metadata->>'quote_number' AS quote_number, metadata->>'total_amount' AS total_amount, metadata->>'status' AS status FROM ai_documents WHERE source_table = 'Quotation' AND metadata->>'status' ILIKE '%approved%' AND metadata->>'project_name' ILIKE '%manila tower%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: how many quotations are pending", "target": "SELECT COUNT(*) AS count FROM ai_documents WHERE source_table = 'Quotation' AND metadata->>'status' ILIKE '%draft%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: list all distinct quotation statuses", "target": "SELECT DISTINCT metadata->>'status' AS status FROM ai_documents WHERE source_table = 'Quotation' AND document_type = 'row' ORDER BY status;"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: total volume delivered for plate ABC-1234", "target": "SELECT SUM((metadata->>'volume')::numeric) AS total_volume FROM ai_documents WHERE source_table = 'QuotationItem' AND metadata->>'plate_no' ILIKE '%ABC-1234%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: show deliveries for DR-001", "target": "SELECT metadata->>'plate_no' AS plate_no, metadata->>'material' AS material, metadata->>'volume' AS volume, metadata->>'line_total' AS line_total FROM ai_documents WHERE source_table = 'QuotationItem' AND metadata->>'dr_no' ILIKE '%DR-001%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: total line total for gravel deliveries from montalban", "target": "SELECT SUM((metadata->>'line_total')::numeric) AS total FROM ai_documents WHERE source_table = 'QuotationItem' AND metadata->>'material' ILIKE '%gravel%' AND metadata->>'quarry_location' ILIKE '%montalban%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: how many deliveries used 10-wheeler trucks", "target": "SELECT COUNT(*) AS count FROM ai_documents WHERE source_table = 'QuotationItem' AND metadata->>'truck_type' ILIKE '%10-wheeler%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: compare total volume by material type", "target": "SELECT metadata->>'material' AS material, SUM((metadata->>'volume')::numeric) AS total_volume FROM ai_documents WHERE source_table = 'QuotationItem' AND document_type = 'row' GROUP BY material ORDER BY total_volume DESC;"}
```

### Coverage Checklist

Ensure your generated pairs cover ALL of the following. Aim for the approximate distribution shown:

| Intent Type | Approx. % | Min Pairs (of 5,000) |
|---|---|---|
| list_files | 8% | 400 |
| query_data | 18% | 900 |
| sum | 18% | 900 |
| count | 15% | 750 |
| average | 10% | 500 |
| compare | 10% | 500 |
| list_categories | 10% | 500 |
| date_filter | 11% | 550 |

Ensure coverage of ALL standard metadata columns:
- Expenses: Category ✓, Expenses ✓, Name ✓
- CashFlow: Type ✓, Amount ✓, Category ✓
- Project: project_name ✓, client_name ✓, location ✓, status ✓
- Quotation: quote_number ✓, status ✓, total_amount ✓, project_name ✓
- QuotationItem: plate_no ✓, dr_no ✓, material ✓, quarry_location ✓, truck_type ✓, volume ✓, line_total ✓

Ensure coverage of ALL source tables:
- Expenses (~35%) ✓
- CashFlow (~25%) ✓
- Project (~15%) ✓
- Quotation (~15%) ✓
- QuotationItem (~10%) ✓

Ensure coverage of ALL filter types:
- file_name only ✓
- project_name only ✓
- category only ✓
- name only ✓
- type only (CashFlow) ✓
- status only (Project/Quotation) ✓
- material only (QuotationItem) ✓
- plate_no only (QuotationItem) ✓
- dr_no only (QuotationItem) ✓
- client_name only (Project) ✓
- quote_number only (Quotation) ✓
- quarry_location only (QuotationItem) ✓
- truck_type only (QuotationItem) ✓
- file_name + category ✓
- project_name + status ✓
- category + name ✓
- file_name + project_name + category ✓
- material + quarry_location ✓
- plate_no + dr_no ✓
- quote_number + project_name ✓
- client_name + status ✓
- truck_type + material + quarry_location ✓
- No extra filters (just source_table + document_type) ✓

### Final Instructions

1. Generate exactly 5,000 pairs total
2. Output raw JSONL — one JSON object per line, no code fences, no commentary
3. Every `"input"` must start with the exact Spider schema prefix shown above
4. Every `"target"` must be a valid SELECT-only SQL statement ending with a semicolon
5. Every `"target"` must include `source_table = 'Expenses'`, `source_table = 'CashFlow'`, `source_table = 'Project'`, `source_table = 'Quotation'`, or `source_table = 'QuotationItem'`
6. Every `"target"` must include `document_type = 'file'` or `document_type = 'row'`
7. Use `metadata->>'ColumnName'` for all metadata access
8. Use `ILIKE` with `%` wildcards for text matching
9. Cast to `::numeric` for any arithmetic (SUM, AVG, comparisons with numbers) — only for numeric keys: Expenses, Amount, total_amount, volume, line_total
10. Maximize diversity in phrasing, filters, columns, and structure
11. All questions must be in English
12. Include 5–10% of pairs that demonstrate querying custom/dynamic metadata key names (e.g., `metadata->>'Driver'`, `metadata->>'Supplier'`, `metadata->>'Remarks'`) to teach the model to handle arbitrary key names
13. To reach 5,000 unique pairs, vary these dimensions systematically:
    - **Phrasing templates**: Use at least 15–20 different sentence structures per intent type (e.g., "show me", "what is", "can you list", "give me", "I need", "pull up", "find all", "get the", "display", "retrieve", "how much", "what's the total", "break down", "summarize", "tell me about")
    - **Entity diversity**: Use at least 50 unique file names, 30 project names, 20 person names, 15 material types, 10 quarry locations, 15 plate numbers, 15 DR numbers, 10 client names, 10 quote numbers
    - **Numeric thresholds**: Vary comparison values (> 1000, > 5000, > 10000, < 500, BETWEEN ranges, etc.)
    - **GROUP BY variations**: Include GROUP BY with ORDER BY ASC/DESC, LIMIT, HAVING clauses
    - **Subquery patterns**: Include a small set (2–3%) with subqueries (e.g., "expenses above average", "projects with most quotations")
    - **Multi-table awareness**: Include 3–5% of pairs that use UNION to combine results from multiple source tables
    - **NULL handling**: Include 1–2% of pairs that check for NULL metadata values (e.g., "entries without a category", `metadata->>'Category' IS NULL`)
