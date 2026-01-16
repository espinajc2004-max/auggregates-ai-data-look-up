-- ============================================
-- 20260128_fix_ai_indexing.sql
-- Fix AI Indexing Issues
-- 1. Include file_name in searchable_text
-- 2. Index QuotationItems (DR numbers, materials)
-- ============================================

-- Drop old function
DROP FUNCTION IF EXISTS ai_index_all_documents();

-- Create improved indexing function
CREATE OR REPLACE FUNCTION ai_index_all_documents()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    total_count INTEGER := 0;
    expense_count INTEGER := 0;
    cashflow_count INTEGER := 0;
    quotation_count INTEGER := 0;
    quotation_item_count INTEGER := 0;
BEGIN
    DELETE FROM ai_documents;
    
    -- ========================================
    -- CASHFLOW - Include file_name in searchable_text
    -- ========================================
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'CashFlow', 
        cfcv.row_id, 
        cf.id, 
        cf.file_name, 
        cf.project_id, 
        p.project_name,
        -- FIXED: Include file_name in searchable_text
        COALESCE(cf.file_name, '') || ' ' || COALESCE(cf.description, '') || ' ' || string_agg(COALESCE(cfcv.value, ''), ' '),
        jsonb_object_agg(cfc.name, COALESCE(cfcv.value, ''))
    FROM "CashFlowCellValue" cfcv
    JOIN "CashFlowColumn" cfc ON cfcv.column_id = cfc.id
    JOIN "CashFlowCustomTable" cfct ON cfc.template_id = cfct.id
    JOIN "CashFlow" cf ON cfct.cash_flow_id = cf.id
    LEFT JOIN "Project" p ON cf.project_id = p.id
    WHERE cfcv.value IS NOT NULL AND cfcv.value != ''
    GROUP BY cfcv.row_id, cf.id, cf.file_name, cf.description, cf.project_id, p.project_name
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        searchable_text = EXCLUDED.searchable_text, 
        metadata = EXCLUDED.metadata, 
        updated_at = NOW();
    GET DIAGNOSTICS cashflow_count = ROW_COUNT;
    
    -- ========================================
    -- EXPENSES - Include file_name in searchable_text
    -- ========================================
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'Expenses', 
        ecv.row_id, 
        e.id, 
        e.file_name, 
        e.project_id, 
        p.project_name,
        -- FIXED: Include file_name in searchable_text
        COALESCE(e.file_name, '') || ' ' || COALESCE(e.description, '') || ' ' || string_agg(COALESCE(ecv.value, ''), ' '),
        jsonb_object_agg(ec.name, COALESCE(ecv.value, ''))
    FROM "ExpensesCellValue" ecv
    JOIN "ExpensesColumn" ec ON ecv.column_id = ec.id
    JOIN "ExpensesTableTemplate" ett ON ec.template_id = ett.id
    JOIN "Expenses" e ON ett.expense_id = e.id
    LEFT JOIN "Project" p ON e.project_id = p.id
    WHERE ecv.value IS NOT NULL AND ecv.value != ''
    GROUP BY ecv.row_id, e.id, e.file_name, e.description, e.project_id, p.project_name
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        searchable_text = EXCLUDED.searchable_text, 
        metadata = EXCLUDED.metadata, 
        updated_at = NOW();
    GET DIAGNOSTICS expense_count = ROW_COUNT;
    
    -- ========================================
    -- QUOTATIONS - Main quotation records
    -- ========================================
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'Quotation',
        q.id,
        q.id,
        q.quote_number,
        q.project_id,
        COALESCE(p.project_name, q.snap_project_name),
        -- Include quote_number, project, location, contact, status
        COALESCE(q.quote_number, '') || ' ' || 
        COALESCE(p.project_name, q.snap_project_name, '') || ' ' || 
        COALESCE(q.snap_location, p.location, '') || ' ' || 
        COALESCE(q.snap_contact, '') || ' ' || 
        COALESCE(q.status, ''),
        jsonb_build_object(
            'quote_number', q.quote_number,
            'project_name', COALESCE(p.project_name, q.snap_project_name),
            'location', COALESCE(q.snap_location, p.location),
            'contact', q.snap_contact,
            'status', q.status,
            'total_amount', q.total_amount
        )
    FROM "Quotation" q
    LEFT JOIN "Project" p ON q.project_id = p.id
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        searchable_text = EXCLUDED.searchable_text, 
        metadata = EXCLUDED.metadata, 
        updated_at = NOW();
    GET DIAGNOSTICS quotation_count = ROW_COUNT;
    
    -- ========================================
    -- QUOTATION ITEMS - NEW! Index DR numbers, materials, plate numbers
    -- ========================================
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'QuotationItem',
        qi.id,
        q.id,
        q.quote_number,
        q.project_id,
        COALESCE(p.project_name, q.snap_project_name),
        -- CRITICAL: Include DR number, plate number, material, quote number
        COALESCE(q.quote_number, '') || ' ' || 
        COALESCE(qi.dr_no, '') || ' ' || 
        COALESCE(qi.plate_no, '') || ' ' || 
        COALESCE(qi.material, '') || ' ' || 
        COALESCE(qi.source_quarry, '') || ' ' || 
        COALESCE(qi.truck_type, ''),
        jsonb_build_object(
            'quote_number', q.quote_number,
            'dr_no', qi.dr_no,
            'plate_no', qi.plate_no,
            'trip_date', qi.trip_date,
            'material', qi.material,
            'source_quarry', qi.source_quarry,
            'truck_type', qi.truck_type,
            'volume', qi.volume,
            'line_total', qi.line_total
        )
    FROM "QuotationItem" qi
    JOIN "Quotation" q ON qi.quotation_id = q.id
    LEFT JOIN "Project" p ON q.project_id = p.id
    WHERE qi.dr_no IS NOT NULL OR qi.material IS NOT NULL
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        searchable_text = EXCLUDED.searchable_text, 
        metadata = EXCLUDED.metadata, 
        updated_at = NOW();
    GET DIAGNOSTICS quotation_item_count = ROW_COUNT;
    
    total_count := cashflow_count + expense_count + quotation_count + quotation_item_count;
    
    RAISE NOTICE 'Indexed % documents: Expenses=%, CashFlow=%, Quotations=%, QuotationItems=%', 
        total_count, expense_count, cashflow_count, quotation_count, quotation_item_count;
    
    RETURN total_count;
END;
$$;

-- Run the indexing
SELECT ai_index_all_documents();

-- Grant permissions
GRANT EXECUTE ON FUNCTION ai_index_all_documents() TO authenticated, service_role;

-- Verify results
SELECT 
    source_table,
    COUNT(*) as count
FROM ai_documents
GROUP BY source_table
ORDER BY source_table;
