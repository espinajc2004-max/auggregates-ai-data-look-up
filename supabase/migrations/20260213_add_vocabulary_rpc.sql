-- Add ai_get_vocabulary RPC function
-- Returns all vocabulary data in one call for better performance

CREATE OR REPLACE FUNCTION ai_get_vocabulary()
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result json;
BEGIN
    -- Aggregate all vocabulary data into a single JSON object
    SELECT json_build_object(
        'projects', (
            SELECT COALESCE(json_agg(DISTINCT project_name), '[]'::json)
            FROM ai_documents
            WHERE project_name IS NOT NULL
        ),
        'project_locations', (
            SELECT COALESCE(json_agg(DISTINCT metadata->>'location'), '[]'::json)
            FROM ai_documents
            WHERE metadata->>'location' IS NOT NULL
        ),
        'expense_files', (
            SELECT COALESCE(json_agg(DISTINCT file_name), '[]'::json)
            FROM ai_documents
            WHERE source_table = 'Expenses' AND file_name IS NOT NULL
        ),
        'cashflow_files', (
            SELECT COALESCE(json_agg(DISTINCT file_name), '[]'::json)
            FROM ai_documents
            WHERE source_table = 'CashFlow' AND file_name IS NOT NULL
        ),
        'expense_categories', (
            SELECT COALESCE(json_agg(DISTINCT metadata->>'Category'), '[]'::json)
            FROM ai_documents
            WHERE source_table = 'Expenses' AND metadata->>'Category' IS NOT NULL
        ),
        'cashflow_categories', (
            SELECT COALESCE(json_agg(DISTINCT metadata->>'Type'), '[]'::json)
            FROM ai_documents
            WHERE source_table = 'CashFlow' AND metadata->>'Type' IS NOT NULL
        )
    ) INTO result;
    
    RETURN result;
END;
$$;

-- Grant execute permission to anon and authenticated roles
GRANT EXECUTE ON FUNCTION ai_get_vocabulary() TO anon, authenticated;

COMMENT ON FUNCTION ai_get_vocabulary IS 'Returns all vocabulary data for entity matching in one call';
