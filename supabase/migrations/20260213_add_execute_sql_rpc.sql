-- Add execute_sql RPC function for Text-to-SQL feature
-- This allows the Python client to execute raw SQL queries

CREATE OR REPLACE FUNCTION execute_sql(query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result json;
BEGIN
    -- Execute the query and return results as JSON
    EXECUTE 'SELECT json_agg(row_to_json(t)) FROM (' || query || ') t' INTO result;
    
    -- Return empty array if no results
    IF result IS NULL THEN
        result := '[]'::json;
    END IF;
    
    RETURN result;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'SQL execution error: %', SQLERRM;
END;
$$;

-- Grant execute permission to anon and authenticated roles
GRANT EXECUTE ON FUNCTION execute_sql(text) TO anon, authenticated;

COMMENT ON FUNCTION execute_sql IS 'Execute raw SQL queries for Text-to-SQL analytics feature';
