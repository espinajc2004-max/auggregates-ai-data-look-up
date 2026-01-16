-- ============================================
-- 20260126_init_ai_search.sql
-- AI Data Lookup - Complete Schema
-- ============================================

-- 1. Create AI Documents Table
CREATE TABLE IF NOT EXISTS ai_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table TEXT NOT NULL,
    source_id TEXT NOT NULL,
    file_id TEXT,
    file_name TEXT,
    project_id TEXT,
    project_name TEXT,
    searchable_text TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', COALESCE(searchable_text, '') || ' ' || COALESCE(file_name, ''))
    ) STORED,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_source UNIQUE (source_table, source_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ai_documents_search ON ai_documents USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_ai_documents_source ON ai_documents (source_table);
CREATE INDEX IF NOT EXISTS idx_ai_documents_project ON ai_documents (project_id);

-- 2. Indexing Function
CREATE OR REPLACE FUNCTION ai_index_all_documents()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    total_count INTEGER := 0;
    expense_count INTEGER := 0;
    cashflow_count INTEGER := 0;
BEGIN
    DELETE FROM ai_documents;
    
    -- CashFlow
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'CashFlow', cfcv.row_id, cf.id, cf.file_name, cf.project_id, p.project_name,
        string_agg(COALESCE(cfcv.value, ''), ' '),
        jsonb_object_agg(cfc.name, COALESCE(cfcv.value, ''))
    FROM "CashFlowCellValue" cfcv
    JOIN "CashFlowColumn" cfc ON cfcv.column_id = cfc.id
    JOIN "CashFlowCustomTable" cfct ON cfc.template_id = cfct.id
    JOIN "CashFlow" cf ON cfct.cash_flow_id = cf.id
    LEFT JOIN "Project" p ON cf.project_id = p.id
    WHERE cfcv.value IS NOT NULL AND cfcv.value != ''
    GROUP BY cfcv.row_id, cf.id, cf.file_name, cf.project_id, p.project_name
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();
    GET DIAGNOSTICS cashflow_count = ROW_COUNT;
    
    -- Expenses
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'Expenses', ecv.row_id, e.id, e.file_name, e.project_id, p.project_name,
        string_agg(COALESCE(ecv.value, ''), ' '),
        jsonb_object_agg(ec.name, COALESCE(ecv.value, ''))
    FROM "ExpensesCellValue" ecv
    JOIN "ExpensesColumn" ec ON ecv.column_id = ec.id
    JOIN "ExpensesTableTemplate" ett ON ec.template_id = ett.id
    JOIN "Expenses" e ON ett.expense_id = e.id
    LEFT JOIN "Project" p ON e.project_id = p.id
    WHERE ecv.value IS NOT NULL AND ecv.value != ''
    GROUP BY ecv.row_id, e.id, e.file_name, e.project_id, p.project_name
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();
    GET DIAGNOSTICS expense_count = ROW_COUNT;
    
    RETURN cashflow_count + expense_count;
END;
$$;

-- 3. Search Function
CREATE OR REPLACE FUNCTION ai_search_universal_v2(
    p_search_term TEXT,
    p_source_table TEXT DEFAULT NULL,
    p_project_id TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    source_table TEXT,
    source_id TEXT,
    file_id TEXT,
    file_name TEXT,
    project_id TEXT,
    project_name TEXT,
    searchable_text TEXT,
    metadata JSONB,
    rank REAL,
    matched_highlights TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ad.id,
        ad.source_table,
        ad.source_id,
        ad.file_id,
        ad.file_name,
        ad.project_id,
        ad.project_name,
        ad.searchable_text,
        ad.metadata,
        ts_rank(ad.search_vector, plainto_tsquery('english', p_search_term)) AS rank,
        ts_headline('english', ad.searchable_text, plainto_tsquery('english', p_search_term), 
            'StartSel=<b>, StopSel=</b>, MaxWords=20, MinWords=5') AS matched_highlights
    FROM ai_documents ad
    WHERE 
        (ad.searchable_text ILIKE '%' || p_search_term || '%'
         OR ad.search_vector @@ plainto_tsquery('english', p_search_term))
        AND (p_source_table IS NULL OR ad.source_table = p_source_table)
        AND (p_project_id IS NULL OR ad.project_id = p_project_id)
        ORDER BY rank DESC, ad.updated_at DESC
        LIMIT p_limit;
END;
$$;

-- 4. List Files Function
CREATE OR REPLACE FUNCTION ai_list_files(p_table_type TEXT DEFAULT 'expenses')
RETURNS TABLE (
    file_id TEXT,
    file_name TEXT,
    project_id TEXT,
    project_name TEXT,
    row_count BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    source TEXT;
BEGIN
    source := CASE 
        WHEN LOWER(p_table_type) = 'expenses' THEN 'Expenses'
        WHEN LOWER(p_table_type) = 'cashflow' THEN 'CashFlow'
        ELSE INITCAP(p_table_type)
    END;
    
    RETURN QUERY
    SELECT 
        ad.file_id,
        ad.file_name,
        ad.project_id,
        ad.project_name,
        COUNT(DISTINCT ad.source_id) AS row_count
    FROM ai_documents ad
    WHERE ad.source_table = source
    GROUP BY ad.file_id, ad.file_name, ad.project_id, ad.project_name
    ORDER BY ad.file_name;
END;
$$;

-- 5. Permissions
GRANT SELECT ON ai_documents TO anon, authenticated, service_role;
GRANT INSERT, UPDATE, DELETE ON ai_documents TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION ai_search_universal_v2(text, text, text, integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION ai_list_files(text) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION ai_index_all_documents() TO authenticated, service_role;

-- RLS
ALTER TABLE ai_documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow read access for all" ON ai_documents FOR SELECT USING (true);
CREATE POLICY "Allow authenticated write" ON ai_documents FOR ALL USING (auth.role() IN ('authenticated', 'service_role'));
