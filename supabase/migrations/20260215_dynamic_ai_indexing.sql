-- ============================================
-- 20260215_dynamic_ai_indexing.sql
-- DYNAMIC AI Document Indexing
--
-- TWO PARTS:
-- 1. Rebuilt ai_index_all_documents() that indexes FILES + PROJECTS 
--    (not just cell data rows) for initial bulk indexing
-- 2. AUTO-INDEX TRIGGERS on all source tables so any INSERT/UPDATE/DELETE
--    automatically updates ai_documents in real-time
--
-- This means: ANY data the user adds through the app is INSTANTLY
-- searchable by the AI — no manual re-indexing needed.
-- ============================================


-- =============================================
-- PART 1: REBUILT BULK INDEXER
-- Indexes: Expenses files, CashFlow files, Projects,
--          Quotations, QuotationItems, + all CellValue rows
-- =============================================

DROP FUNCTION IF EXISTS ai_index_all_documents();

CREATE OR REPLACE FUNCTION ai_index_all_documents()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    total_count INTEGER := 0;
    cnt INTEGER := 0;
BEGIN
    DELETE FROM ai_documents;
    
    -- 1. EXPENSES FILES
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'Expenses', e.id, e.id, e.file_name, e.project_id, p.project_name,
        COALESCE(e.file_name, '') || ' ' || COALESCE(e.description, '') || ' ' || COALESCE(p.project_name, '') || ' expenses file',
        jsonb_build_object('id', e.id, 'file_name', e.file_name, 'description', e.description, 'project_name', p.project_name, 'type', 'file')
    FROM "Expenses" e
    LEFT JOIN "Project" p ON e.project_id = p.id
    WHERE e."isArchived" IS NOT TRUE
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();
    GET DIAGNOSTICS cnt = ROW_COUNT;
    total_count := total_count + cnt;
    
    -- 2. EXPENSES CELL VALUES (row-level data inside expense spreadsheets)
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'Expenses', 'row_' || ecv.row_id, e.id, e.file_name, e.project_id, p.project_name,
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
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();
    GET DIAGNOSTICS cnt = ROW_COUNT;
    total_count := total_count + cnt;
    
    -- 3. CASHFLOW FILES
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'CashFlow', cf.id, cf.id, cf.file_name, cf.project_id, p.project_name,
        COALESCE(cf.file_name, '') || ' ' || COALESCE(cf.description, '') || ' ' || COALESCE(p.project_name, '') || ' cashflow file',
        jsonb_build_object('id', cf.id, 'file_name', cf.file_name, 'description', cf.description, 'project_name', p.project_name, 'type', 'file')
    FROM "CashFlow" cf
    LEFT JOIN "Project" p ON cf.project_id = p.id
    WHERE cf."isArchived" IS NOT TRUE
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();
    GET DIAGNOSTICS cnt = ROW_COUNT;
    total_count := total_count + cnt;
    
    -- 4. CASHFLOW CELL VALUES
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'CashFlow', 'row_' || cfcv.row_id, cf.id, cf.file_name, cf.project_id, p.project_name,
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
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();
    GET DIAGNOSTICS cnt = ROW_COUNT;
    total_count := total_count + cnt;
    
    -- 5. PROJECTS
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'Project', p.id, p.id, p.project_name, p.id, p.project_name,
        COALESCE(p.project_name, '') || ' ' || COALESCE(p.client_name, '') || ' ' || COALESCE(p.location, '') || ' ' || COALESCE(p.status, '') || ' project',
        jsonb_build_object('id', p.id, 'project_name', p.project_name, 'client_name', p.client_name, 'location', p.location, 'status', p.status, 'type', 'project')
    FROM "Project" p
    WHERE p."isArchived" IS NOT TRUE
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();
    GET DIAGNOSTICS cnt = ROW_COUNT;
    total_count := total_count + cnt;
    
    -- 6. QUOTATIONS
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'Quotation', q.id, q.id, q.quote_number, q.project_id, COALESCE(p.project_name, q.snap_project_name),
        COALESCE(q.quote_number, '') || ' ' || COALESCE(p.project_name, q.snap_project_name, '') || ' ' || COALESCE(q.snap_location, '') || ' ' || COALESCE(q.snap_contact, '') || ' ' || COALESCE(q.status, '') || ' quotation',
        jsonb_build_object('id', q.id, 'quote_number', q.quote_number, 'project_name', COALESCE(p.project_name, q.snap_project_name), 'status', q.status, 'total_amount', q.total_amount, 'type', 'quotation')
    FROM "Quotation" q
    LEFT JOIN "Project" p ON q.project_id = p.id
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();
    GET DIAGNOSTICS cnt = ROW_COUNT;
    total_count := total_count + cnt;
    
    -- 7. QUOTATION ITEMS
    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    SELECT 
        'QuotationItem', qi.id, q.id, q.quote_number, q.project_id, COALESCE(p.project_name, q.snap_project_name),
        COALESCE(q.quote_number, '') || ' ' || COALESCE(qi.dr_no, '') || ' ' || COALESCE(qi.plate_no, '') || ' ' || COALESCE(qi.material, '') || ' ' || COALESCE(qi.quarry_location, '') || ' ' || COALESCE(qi.truck_type, ''),
        jsonb_build_object('quote_number', q.quote_number, 'dr_no', qi.dr_no, 'plate_no', qi.plate_no, 'material', qi.material, 'quarry_location', qi.quarry_location, 'truck_type', qi.truck_type, 'volume', qi.volume, 'line_total', qi.line_total, 'type', 'quotation_item')
    FROM "QuotationItem" qi
    JOIN "Quotation" q ON qi.quotation_id = q.id
    LEFT JOIN "Project" p ON q.project_id = p.id
    WHERE qi.dr_no IS NOT NULL OR qi.material IS NOT NULL
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();
    GET DIAGNOSTICS cnt = ROW_COUNT;
    total_count := total_count + cnt;
    
    RETURN total_count;
END;
$$;

GRANT EXECUTE ON FUNCTION ai_index_all_documents() TO anon, authenticated, service_role;


-- =============================================
-- PART 2: DYNAMIC AUTO-INDEX TRIGGERS
-- These fire on every INSERT/UPDATE/DELETE on source tables
-- so ai_documents stays in sync automatically.
-- =============================================

-- ─── 2A. Expenses File trigger ───────────────────────────────────
CREATE OR REPLACE FUNCTION ai_auto_index_expense_file()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_project_name TEXT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM ai_documents WHERE source_table = 'Expenses' AND source_id = OLD.id;
        RETURN OLD;
    END IF;

    -- Skip archived
    IF NEW."isArchived" = TRUE THEN
        DELETE FROM ai_documents WHERE source_table = 'Expenses' AND source_id = NEW.id;
        RETURN NEW;
    END IF;

    SELECT project_name INTO v_project_name FROM "Project" WHERE id = NEW.project_id;

    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    VALUES (
        'Expenses', NEW.id, NEW.id, NEW.file_name, NEW.project_id, v_project_name,
        COALESCE(NEW.file_name, '') || ' ' || COALESCE(NEW.description, '') || ' ' || COALESCE(v_project_name, '') || ' expenses file',
        jsonb_build_object('id', NEW.id, 'file_name', NEW.file_name, 'description', NEW.description, 'project_name', v_project_name, 'type', 'file')
    )
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        file_name = EXCLUDED.file_name, project_id = EXCLUDED.project_id, project_name = EXCLUDED.project_name,
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_index_expense_file ON "Expenses";
CREATE TRIGGER trg_ai_index_expense_file
    AFTER INSERT OR UPDATE OR DELETE ON "Expenses"
    FOR EACH ROW EXECUTE FUNCTION ai_auto_index_expense_file();


-- ─── 2B. CashFlow File trigger ───────────────────────────────────
CREATE OR REPLACE FUNCTION ai_auto_index_cashflow_file()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_project_name TEXT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM ai_documents WHERE source_table = 'CashFlow' AND source_id = OLD.id;
        RETURN OLD;
    END IF;

    IF NEW."isArchived" = TRUE THEN
        DELETE FROM ai_documents WHERE source_table = 'CashFlow' AND source_id = NEW.id;
        RETURN NEW;
    END IF;

    SELECT project_name INTO v_project_name FROM "Project" WHERE id = NEW.project_id;

    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    VALUES (
        'CashFlow', NEW.id, NEW.id, NEW.file_name, NEW.project_id, v_project_name,
        COALESCE(NEW.file_name, '') || ' ' || COALESCE(NEW.description, '') || ' ' || COALESCE(v_project_name, '') || ' cashflow file',
        jsonb_build_object('id', NEW.id, 'file_name', NEW.file_name, 'description', NEW.description, 'project_name', v_project_name, 'type', 'file')
    )
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        file_name = EXCLUDED.file_name, project_id = EXCLUDED.project_id, project_name = EXCLUDED.project_name,
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_index_cashflow_file ON "CashFlow";
CREATE TRIGGER trg_ai_index_cashflow_file
    AFTER INSERT OR UPDATE OR DELETE ON "CashFlow"
    FOR EACH ROW EXECUTE FUNCTION ai_auto_index_cashflow_file();


-- ─── 2C. Project trigger ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION ai_auto_index_project()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM ai_documents WHERE source_table = 'Project' AND source_id = OLD.id;
        RETURN OLD;
    END IF;

    IF NEW."isArchived" = TRUE THEN
        DELETE FROM ai_documents WHERE source_table = 'Project' AND source_id = NEW.id;
        RETURN NEW;
    END IF;

    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    VALUES (
        'Project', NEW.id, NEW.id, NEW.project_name, NEW.id, NEW.project_name,
        COALESCE(NEW.project_name, '') || ' ' || COALESCE(NEW.client_name, '') || ' ' || COALESCE(NEW.location, '') || ' ' || COALESCE(NEW.status, '') || ' project',
        jsonb_build_object('id', NEW.id, 'project_name', NEW.project_name, 'client_name', NEW.client_name, 'location', NEW.location, 'status', NEW.status, 'type', 'project')
    )
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        file_name = EXCLUDED.file_name, project_name = EXCLUDED.project_name,
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_index_project ON "Project";
CREATE TRIGGER trg_ai_index_project
    AFTER INSERT OR UPDATE OR DELETE ON "Project"
    FOR EACH ROW EXECUTE FUNCTION ai_auto_index_project();


-- ─── 2D. ExpensesCellValue trigger (row data inside expense spreadsheets) ─
CREATE OR REPLACE FUNCTION ai_auto_index_expense_cell()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_row_id TEXT;
    v_file_id TEXT;
    v_file_name TEXT;
    v_description TEXT;
    v_project_id TEXT;
    v_project_name TEXT;
    v_searchable TEXT;
    v_metadata JSONB;
BEGIN
    -- Get the row_id
    IF TG_OP = 'DELETE' THEN
        v_row_id := OLD.row_id;
    ELSE
        v_row_id := NEW.row_id;
    END IF;

    -- Re-aggregate ALL cell values for this row (handles insert, update, delete)
    SELECT 
        e.id, e.file_name, e.description, e.project_id, p.project_name,
        COALESCE(e.file_name, '') || ' ' || COALESCE(e.description, '') || ' ' || string_agg(COALESCE(ecv.value, ''), ' '),
        jsonb_object_agg(ec.name, COALESCE(ecv.value, ''))
    INTO v_file_id, v_file_name, v_description, v_project_id, v_project_name, v_searchable, v_metadata
    FROM "ExpensesCellValue" ecv
    JOIN "ExpensesColumn" ec ON ecv.column_id = ec.id
    JOIN "ExpensesTableTemplate" ett ON ec.template_id = ett.id
    JOIN "Expenses" e ON ett.expense_id = e.id
    LEFT JOIN "Project" p ON e.project_id = p.id
    WHERE ecv.row_id = v_row_id AND ecv.value IS NOT NULL AND ecv.value != ''
    GROUP BY e.id, e.file_name, e.description, e.project_id, p.project_name;

    IF v_searchable IS NULL THEN
        -- All cells for this row deleted
        DELETE FROM ai_documents WHERE source_table = 'Expenses' AND source_id = 'row_' || v_row_id;
    ELSE
        INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
        VALUES ('Expenses', 'row_' || v_row_id, v_file_id, v_file_name, v_project_id, v_project_name, v_searchable, v_metadata)
        ON CONFLICT (source_table, source_id) DO UPDATE SET
            file_id = EXCLUDED.file_id, file_name = EXCLUDED.file_name, project_id = EXCLUDED.project_id, project_name = EXCLUDED.project_name,
            searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_index_expense_cell ON "ExpensesCellValue";
CREATE TRIGGER trg_ai_index_expense_cell
    AFTER INSERT OR UPDATE OR DELETE ON "ExpensesCellValue"
    FOR EACH ROW EXECUTE FUNCTION ai_auto_index_expense_cell();


-- ─── 2E. CashFlowCellValue trigger ───────────────────────────────
CREATE OR REPLACE FUNCTION ai_auto_index_cashflow_cell()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_row_id TEXT;
    v_file_id TEXT;
    v_file_name TEXT;
    v_description TEXT;
    v_project_id TEXT;
    v_project_name TEXT;
    v_searchable TEXT;
    v_metadata JSONB;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_row_id := OLD.row_id;
    ELSE
        v_row_id := NEW.row_id;
    END IF;

    SELECT 
        cf.id, cf.file_name, cf.description, cf.project_id, p.project_name,
        COALESCE(cf.file_name, '') || ' ' || COALESCE(cf.description, '') || ' ' || string_agg(COALESCE(cfcv.value, ''), ' '),
        jsonb_object_agg(cfc.name, COALESCE(cfcv.value, ''))
    INTO v_file_id, v_file_name, v_description, v_project_id, v_project_name, v_searchable, v_metadata
    FROM "CashFlowCellValue" cfcv
    JOIN "CashFlowColumn" cfc ON cfcv.column_id = cfc.id
    JOIN "CashFlowCustomTable" cfct ON cfc.template_id = cfct.id
    JOIN "CashFlow" cf ON cfct.cash_flow_id = cf.id
    LEFT JOIN "Project" p ON cf.project_id = p.id
    WHERE cfcv.row_id = v_row_id AND cfcv.value IS NOT NULL AND cfcv.value != ''
    GROUP BY cf.id, cf.file_name, cf.description, cf.project_id, p.project_name;

    IF v_searchable IS NULL THEN
        DELETE FROM ai_documents WHERE source_table = 'CashFlow' AND source_id = 'row_' || v_row_id;
    ELSE
        INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
        VALUES ('CashFlow', 'row_' || v_row_id, v_file_id, v_file_name, v_project_id, v_project_name, v_searchable, v_metadata)
        ON CONFLICT (source_table, source_id) DO UPDATE SET
            file_id = EXCLUDED.file_id, file_name = EXCLUDED.file_name, project_id = EXCLUDED.project_id, project_name = EXCLUDED.project_name,
            searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_index_cashflow_cell ON "CashFlowCellValue";
CREATE TRIGGER trg_ai_index_cashflow_cell
    AFTER INSERT OR UPDATE OR DELETE ON "CashFlowCellValue"
    FOR EACH ROW EXECUTE FUNCTION ai_auto_index_cashflow_cell();


-- ─── 2F. Quotation trigger ───────────────────────────────────────
CREATE OR REPLACE FUNCTION ai_auto_index_quotation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_project_name TEXT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM ai_documents WHERE source_table = 'Quotation' AND source_id = OLD.id;
        RETURN OLD;
    END IF;

    SELECT project_name INTO v_project_name FROM "Project" WHERE id = NEW.project_id;

    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    VALUES (
        'Quotation', NEW.id, NEW.id, NEW.quote_number, NEW.project_id, COALESCE(v_project_name, NEW.snap_project_name),
        COALESCE(NEW.quote_number, '') || ' ' || COALESCE(v_project_name, NEW.snap_project_name, '') || ' ' || COALESCE(NEW.snap_location, '') || ' ' || COALESCE(NEW.snap_contact, '') || ' ' || COALESCE(NEW.status, '') || ' quotation',
        jsonb_build_object('id', NEW.id, 'quote_number', NEW.quote_number, 'project_name', COALESCE(v_project_name, NEW.snap_project_name), 'status', NEW.status, 'total_amount', NEW.total_amount, 'type', 'quotation')
    )
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        file_name = EXCLUDED.file_name, project_id = EXCLUDED.project_id, project_name = EXCLUDED.project_name,
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_index_quotation ON "Quotation";
CREATE TRIGGER trg_ai_index_quotation
    AFTER INSERT OR UPDATE OR DELETE ON "Quotation"
    FOR EACH ROW EXECUTE FUNCTION ai_auto_index_quotation();


-- ─── 2G. QuotationItem trigger ───────────────────────────────────
CREATE OR REPLACE FUNCTION ai_auto_index_quotation_item()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_quote_number TEXT;
    v_project_id TEXT;
    v_project_name TEXT;
    v_rec RECORD;
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM ai_documents WHERE source_table = 'QuotationItem' AND source_id = OLD.id;
        RETURN OLD;
    END IF;

    SELECT q.quote_number, q.project_id, COALESCE(p.project_name, q.snap_project_name)
    INTO v_quote_number, v_project_id, v_project_name
    FROM "Quotation" q
    LEFT JOIN "Project" p ON q.project_id = p.id
    WHERE q.id = NEW.quotation_id;

    INSERT INTO ai_documents (source_table, source_id, file_id, file_name, project_id, project_name, searchable_text, metadata)
    VALUES (
        'QuotationItem', NEW.id, NEW.quotation_id, v_quote_number, v_project_id, v_project_name,
        COALESCE(v_quote_number, '') || ' ' || COALESCE(NEW.dr_no, '') || ' ' || COALESCE(NEW.plate_no, '') || ' ' || COALESCE(NEW.material, '') || ' ' || COALESCE(NEW.quarry_location, '') || ' ' || COALESCE(NEW.truck_type, ''),
        jsonb_build_object('quote_number', v_quote_number, 'dr_no', NEW.dr_no, 'plate_no', NEW.plate_no, 'material', NEW.material, 'quarry_location', NEW.quarry_location, 'truck_type', NEW.truck_type, 'volume', NEW.volume, 'line_total', NEW.line_total, 'type', 'quotation_item')
    )
    ON CONFLICT (source_table, source_id) DO UPDATE SET
        file_name = EXCLUDED.file_name, project_id = EXCLUDED.project_id, project_name = EXCLUDED.project_name,
        searchable_text = EXCLUDED.searchable_text, metadata = EXCLUDED.metadata, updated_at = NOW();

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_index_quotation_item ON "QuotationItem";
CREATE TRIGGER trg_ai_index_quotation_item
    AFTER INSERT OR UPDATE OR DELETE ON "QuotationItem"
    FOR EACH ROW EXECUTE FUNCTION ai_auto_index_quotation_item();


-- =============================================
-- PART 3: INITIAL BULK INDEX (run once now)
-- =============================================
SELECT ai_index_all_documents();
