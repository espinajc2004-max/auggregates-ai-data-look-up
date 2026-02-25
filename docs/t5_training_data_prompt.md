# T5 Training Data Generation Prompt

## Purpose

Use this prompt with an external AI (ChatGPT, Claude, etc.) to generate 1,000–3,000 diverse English training pairs for fine-tuning the T5-LM-Large-text2sql-spider model. The model translates natural language questions into SQL queries against our `ai_documents` table.

Copy everything below the line into the AI chat.

---

## PROMPT START

You are a training data generator for a text-to-SQL model. Generate between 1,000 and 3,000 diverse English training pairs in JSONL format. Each pair maps a natural language question to a SQL query against a PostgreSQL database.

### Database Schema

The database has a single table:

```sql
CREATE TABLE ai_documents (
    id UUID PRIMARY KEY,
    source_table TEXT NOT NULL,        -- 'Expenses' or 'CashFlow'
    file_name TEXT,                     -- name of the uploaded file
    project_name TEXT,                  -- name of the project
    searchable_text TEXT NOT NULL,      -- full-text search content
    metadata JSONB DEFAULT '{}',        -- structured data (see keys below)
    document_type TEXT DEFAULT 'row'    -- 'file' for file-level docs, 'row' for data rows
);
```

### Metadata JSONB Keys

The `metadata` column is a JSONB object. The keys depend on `source_table`:

**Expenses metadata keys:**
| Key | Description | Example Values |
|-----|-------------|----------------|
| Category | Expense category | "Fuel", "Labor", "Materials", "Equipment", "Food", "Transportation", "Office Supplies" |
| Expenses | Monetary amount (text) | "1500.00", "250.50", "10000" |
| Date | Date string | "2026-01-15", "2026-03-22", "January 2026" |
| Description | Line item description | "Diesel for backhoe", "Electrician wages", "Cement bags" |
| Supplier | Vendor/supplier name | "ABC Hardware", "Metro Gas Station", "Juan's Welding" |
| Method | Payment method | "Cash", "Bank Transfer", "Check", "Credit Card" |
| Remarks | Additional notes | "Urgent purchase", "Monthly delivery", "Discounted" |
| Name | Person/entity name | "John Doe", "Maria Santos", "Pedro Cruz" |

**CashFlow metadata keys:**
| Key | Description | Example Values |
|-----|-------------|----------------|
| Inflow | Money received (text) | "50000.00", "12500", "0" |
| Outflow | Money spent (text) | "30000.00", "8750.50", "0" |
| Balance | Running balance (text) | "20000.00", "115000", "5250.75" |
| Date | Date string | "2026-02-01", "2026-06-15" |
| Remarks | Additional notes | "Client payment", "Material purchase", "Loan disbursement" |
| Description | Transaction description | "Payment from Client A", "Purchased steel bars", "Office rent" |

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
3. **sum** — Sum monetary values (Expenses, Inflow, Outflow)
4. **count** — Count rows matching criteria
5. **average** — Average monetary values
6. **compare** — Compare values across files, projects, or categories
7. **list_categories** — List distinct values of a metadata column
8. **date_filter** — Filter data by date or date range

### SQL Rules (CRITICAL — follow these exactly)

1. **Always include `source_table` filter**: Every query must filter by `source_table = 'Expenses'` or `source_table = 'CashFlow'` (or both with UNION if the question is about both).

2. **Always include `document_type` filter**:
   - For `list_files` intent: use `document_type = 'file'`
   - For all data queries (query_data, sum, count, average, compare, list_categories, date_filter): use `document_type = 'row'`

3. **Use JSONB access patterns for metadata columns**: Access metadata values using `metadata->>'ColumnName'` (double arrow for text extraction). Examples:
   - `metadata->>'Category'`
   - `metadata->>'Expenses'`
   - `metadata->>'Date'`
   - `metadata->>'Supplier'`
   - `metadata->>'Inflow'`

4. **Cast numeric values for aggregation**: When summing or averaging, cast to numeric:
   - `SUM((metadata->>'Expenses')::numeric)`
   - `AVG((metadata->>'Inflow')::numeric)`

5. **Use ILIKE for text matching**: For category, supplier, description, name filters:
   - `metadata->>'Category' ILIKE '%fuel%'`
   - `metadata->>'Supplier' ILIKE '%abc hardware%'`

6. **SELECT only**: Every target SQL must be a SELECT statement. Never generate INSERT, UPDATE, DELETE, DROP, or any write operation.

7. **Reference only `ai_documents`**: Never reference any other table.

8. **Use standard column references for non-metadata columns**: `file_name`, `project_name`, `source_table`, `document_type` are regular columns, not inside metadata.

### Filter Combinations

Generate pairs using these filters individually AND in combination:

- **file_name** filter: `file_name ILIKE '%...'`
- **project_name** filter: `project_name ILIKE '%...'`
- **category** filter: `metadata->>'Category' ILIKE '%...'`
- **date** filter: `metadata->>'Date' >= '...' AND metadata->>'Date' <= '...'` or `metadata->>'Date' ILIKE '%...'`
- **supplier** filter: `metadata->>'Supplier' ILIKE '%...'`

Combined filter examples:
- file_name + category
- project_name + date
- category + supplier
- file_name + project_name + category
- date + category + file_name

### Output Format

Output one JSON object per line (JSONL format). Each object has exactly two keys:

```json
{"input": "tables: ai_documents (...) | query: <question>", "target": "SELECT ...;"}
```

Do NOT wrap the output in a code block. Output raw JSONL lines only.

### Diversity Guidelines

- **Vary phrasing**: Use different ways to ask the same type of question. Examples for sum: "total expenses", "how much was spent", "what's the sum of", "add up all", "give me the total", "calculate total cost"
- **Vary entity names**: Use diverse file names (e.g., "main expenses", "Q1 report", "site A costs", "manila tower"), project names (e.g., "Project Alpha", "Highway 5", "Building C", "Phase 2"), supplier names, category names
- **Vary column usage**: Don't always query the same metadata columns. Mix Category, Expenses, Date, Description, Supplier, Method, Remarks, Name for Expenses. Mix Inflow, Outflow, Balance, Date, Remarks, Description for CashFlow
- **Vary filter combinations**: Some queries with no filters beyond source_table, some with one filter, some with two, some with three or more
- **Vary SQL structure**: Use different SELECT columns, different WHERE clause orderings, different aggregation patterns
- **Avoid repetitive patterns**: Each pair should be meaningfully different from every other pair. Don't just swap one word — change the sentence structure, the filters, the columns, and the intent
- **Mix source tables**: Roughly 60% Expenses queries, 40% CashFlow queries
- **Include edge cases**: Queries with no filters, queries with many filters, queries asking about specific dates, date ranges, specific amounts

### Example Training Pairs

Here are 15 example pairs demonstrating the expected format and variety. Your generated pairs should follow this pattern but be much more diverse:

```jsonl
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: show all expense files", "target": "SELECT id, file_name, project_name FROM ai_documents WHERE source_table = 'Expenses' AND document_type = 'file';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: what are the total fuel expenses", "target": "SELECT SUM((metadata->>'Expenses')::numeric) AS total FROM ai_documents WHERE source_table = 'Expenses' AND metadata->>'Category' ILIKE '%fuel%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: how many labor entries are in project alpha", "target": "SELECT COUNT(*) AS count FROM ai_documents WHERE source_table = 'Expenses' AND metadata->>'Category' ILIKE '%labor%' AND project_name ILIKE '%alpha%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: list all categories in the main expenses file", "target": "SELECT DISTINCT metadata->>'Category' AS category FROM ai_documents WHERE source_table = 'Expenses' AND file_name ILIKE '%main expenses%' AND document_type = 'row' ORDER BY category;"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: show expenses from january 2026", "target": "SELECT metadata->>'Category' AS category, metadata->>'Expenses' AS amount, metadata->>'Description' AS description, metadata->>'Date' AS date FROM ai_documents WHERE source_table = 'Expenses' AND metadata->>'Date' >= '2026-01-01' AND metadata->>'Date' <= '2026-01-31' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: compare fuel costs between manila tower and building c", "target": "SELECT file_name, SUM((metadata->>'Expenses')::numeric) AS total FROM ai_documents WHERE source_table = 'Expenses' AND metadata->>'Category' ILIKE '%fuel%' AND file_name IN ('manila tower', 'building c') AND document_type = 'row' GROUP BY file_name;"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: average expense amount for materials supplied by abc hardware", "target": "SELECT AVG((metadata->>'Expenses')::numeric) AS average FROM ai_documents WHERE source_table = 'Expenses' AND metadata->>'Category' ILIKE '%materials%' AND metadata->>'Supplier' ILIKE '%abc hardware%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: get all rows from the q1 report file", "target": "SELECT metadata->>'Category' AS category, metadata->>'Expenses' AS amount, metadata->>'Date' AS date, metadata->>'Description' AS description, metadata->>'Supplier' AS supplier FROM ai_documents WHERE source_table = 'Expenses' AND file_name ILIKE '%q1 report%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: list all cashflow files", "target": "SELECT id, file_name, project_name FROM ai_documents WHERE source_table = 'CashFlow' AND document_type = 'file';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: total inflow for project highway 5", "target": "SELECT SUM((metadata->>'Inflow')::numeric) AS total_inflow FROM ai_documents WHERE source_table = 'CashFlow' AND project_name ILIKE '%highway 5%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: how many cashflow entries have outflow greater than 10000", "target": "SELECT COUNT(*) AS count FROM ai_documents WHERE source_table = 'CashFlow' AND (metadata->>'Outflow')::numeric > 10000 AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: show expenses paid by check from supplier metro gas station", "target": "SELECT metadata->>'Category' AS category, metadata->>'Expenses' AS amount, metadata->>'Date' AS date, metadata->>'Description' AS description FROM ai_documents WHERE source_table = 'Expenses' AND metadata->>'Method' ILIKE '%check%' AND metadata->>'Supplier' ILIKE '%metro gas station%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: what is the average outflow per month in the site a costs file", "target": "SELECT AVG((metadata->>'Outflow')::numeric) AS avg_outflow FROM ai_documents WHERE source_table = 'CashFlow' AND file_name ILIKE '%site a costs%' AND document_type = 'row';"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: compare total expenses between project alpha and project beta", "target": "SELECT project_name, SUM((metadata->>'Expenses')::numeric) AS total FROM ai_documents WHERE source_table = 'Expenses' AND project_name IN ('Project Alpha', 'Project Beta') AND document_type = 'row' GROUP BY project_name;"}
{"input": "tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: find all expense entries by john doe in february 2026", "target": "SELECT metadata->>'Category' AS category, metadata->>'Expenses' AS amount, metadata->>'Description' AS description, metadata->>'Date' AS date FROM ai_documents WHERE source_table = 'Expenses' AND metadata->>'Name' ILIKE '%john doe%' AND metadata->>'Date' >= '2026-02-01' AND metadata->>'Date' <= '2026-02-28' AND document_type = 'row';"}
```

### Coverage Checklist

Ensure your generated pairs cover ALL of the following. Aim for the approximate distribution shown:

| Intent Type | Approx. % | Min Pairs (of 1,500) |
|---|---|---|
| list_files | 8% | 120 |
| query_data | 18% | 270 |
| sum | 18% | 270 |
| count | 15% | 225 |
| average | 10% | 150 |
| compare | 10% | 150 |
| list_categories | 10% | 150 |
| date_filter | 11% | 165 |

Ensure coverage of ALL metadata columns:
- Expenses: Category ✓, Expenses ✓, Date ✓, Description ✓, Supplier ✓, Method ✓, Remarks ✓, Name ✓
- CashFlow: Inflow ✓, Outflow ✓, Balance ✓, Date ✓, Remarks ✓, Description ✓

Ensure coverage of ALL filter types:
- file_name only ✓
- project_name only ✓
- category only ✓
- date only ✓
- supplier only ✓
- file_name + category ✓
- project_name + date ✓
- category + supplier ✓
- file_name + project_name + category ✓
- date + category + file_name ✓
- method + supplier ✓
- name + date ✓
- No extra filters (just source_table + document_type) ✓

### Final Instructions

1. Generate between 1,000 and 3,000 pairs total
2. Output raw JSONL — one JSON object per line, no code fences, no commentary
3. Every `"input"` must start with the exact Spider schema prefix shown above
4. Every `"target"` must be a valid SELECT-only SQL statement ending with a semicolon
5. Every `"target"` must include `source_table = 'Expenses'` or `source_table = 'CashFlow'`
6. Every `"target"` must include `document_type = 'file'` or `document_type = 'row'`
7. Use `metadata->>'ColumnName'` for all metadata access
8. Use `ILIKE` with `%` wildcards for text matching
9. Cast to `::numeric` for any arithmetic (SUM, AVG, comparisons with numbers)
10. Maximize diversity in phrasing, filters, columns, and structure
11. All questions must be in English
