-- Migration: Add vocabulary helper functions
-- Date: 2026-02-17
-- Purpose: Add database functions for vocabulary service

-- Function: Get top categories for an org
CREATE OR REPLACE FUNCTION get_top_categories(
    p_org_id UUID,
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    value TEXT,
    count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        metadata->>'category' as value,
        COUNT(*) as count
    FROM ai_documents
    WHERE org_id = p_org_id
    AND metadata->>'category' IS NOT NULL
    GROUP BY metadata->>'category'
    ORDER BY count DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function: Get top projects for an org
CREATE OR REPLACE FUNCTION get_top_projects(
    p_org_id UUID,
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    value TEXT,
    count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        metadata->>'project' as value,
        COUNT(*) as count
    FROM ai_documents
    WHERE org_id = p_org_id
    AND metadata->>'project' IS NOT NULL
    GROUP BY metadata->>'project'
    ORDER BY count DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function: Get top files for an org
CREATE OR REPLACE FUNCTION get_top_files(
    p_org_id UUID,
    p_project TEXT DEFAULT NULL,
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    value TEXT,
    count BIGINT
) AS $$
BEGIN
    IF p_project IS NULL THEN
        RETURN QUERY
        SELECT 
            metadata->>'file_name' as value,
            COUNT(*) as count
        FROM ai_documents
        WHERE org_id = p_org_id
        AND metadata->>'file_name' IS NOT NULL
        AND document_type = 'file'
        GROUP BY metadata->>'file_name'
        ORDER BY count DESC
        LIMIT p_limit;
    ELSE
        RETURN QUERY
        SELECT 
            metadata->>'file_name' as value,
            COUNT(*) as count
        FROM ai_documents
        WHERE org_id = p_org_id
        AND metadata->>'file_name' IS NOT NULL
        AND metadata->>'project' = p_project
        AND document_type = 'file'
        GROUP BY metadata->>'file_name'
        ORDER BY count DESC
        LIMIT p_limit;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function: Get top payment methods for an org
CREATE OR REPLACE FUNCTION get_top_methods(
    p_org_id UUID,
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    value TEXT,
    count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        UPPER(metadata->>'method') as value,
        COUNT(*) as count
    FROM ai_documents
    WHERE org_id = p_org_id
    AND metadata->>'method' IS NOT NULL
    GROUP BY UPPER(metadata->>'method')
    ORDER BY count DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Add comments
COMMENT ON FUNCTION get_top_categories IS 'Get top categories for an organization with counts';
COMMENT ON FUNCTION get_top_projects IS 'Get top projects for an organization with counts';
COMMENT ON FUNCTION get_top_files IS 'Get top files for an organization with counts (optionally filtered by project)';
COMMENT ON FUNCTION get_top_methods IS 'Get top payment methods for an organization with counts';
