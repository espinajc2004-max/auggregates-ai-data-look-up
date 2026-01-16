-- ============================================
-- 20260213_add_multi_query_search.sql
-- Multi-Query Search Function for OR/AND queries
-- ============================================

-- Multi-Query Search Function
-- Handles queries like "gcash or fuel" by splitting into sub-queries
-- and returning grouped results
CREATE OR REPLACE FUNCTION ai_search_multi_query(
    p_query TEXT,
    p_source_table TEXT DEFAULT NULL,
    p_project_id TEXT DEFAULT NULL,
    p_limit_per_query INTEGER DEFAULT 10
)
RETURNS TABLE (
    sub_query_index INTEGER,
    sub_query_text TEXT,
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
DECLARE
    sub_queries TEXT[];
    sub_query TEXT;
    query_index INTEGER := 1;
    query_lower TEXT;
BEGIN
    -- Normalize query
    query_lower := LOWER(TRIM(p_query));
    
    -- Split by OR operators (English: "or", Tagalog: "o")
    -- Replace " o " with " or " for uniform processing
    query_lower := REGEXP_REPLACE(query_lower, '\s+o\s+', ' or ', 'g');
    
    -- Split by " or "
    IF query_lower LIKE '% or %' THEN
        sub_queries := STRING_TO_ARRAY(query_lower, ' or ');
    -- Split by AND operators (English: "and", Tagalog: "at")
    ELSIF query_lower LIKE '% and %' OR query_lower LIKE '% at %' THEN
        -- For AND queries, treat as single query (search for all terms together)
        sub_queries := ARRAY[query_lower];
    -- Split by comma
    ELSIF query_lower LIKE '%,%' THEN
        sub_queries := STRING_TO_ARRAY(query_lower, ',');
    ELSE
        -- Single query
        sub_queries := ARRAY[query_lower];
    END IF;
    
    -- Process each sub-query
    FOREACH sub_query IN ARRAY sub_queries
    LOOP
        -- Trim whitespace
        sub_query := TRIM(sub_query);
        
        -- Skip empty queries
        IF sub_query = '' THEN
            CONTINUE;
        END IF;
        
        -- Search for this sub-query
        RETURN QUERY
        SELECT 
            query_index AS sub_query_index,
            sub_query AS sub_query_text,
            ad.id,
            ad.source_table,
            ad.source_id,
            ad.file_id,
            ad.file_name,
            ad.project_id,
            ad.project_name,
            ad.searchable_text,
            ad.metadata,
            ts_rank(ad.search_vector, plainto_tsquery('english', sub_query)) AS rank,
            ts_headline('english', ad.searchable_text, plainto_tsquery('english', sub_query), 
                'StartSel=<b>, StopSel=</b>, MaxWords=20, MinWords=5') AS matched_highlights
        FROM ai_documents ad
        WHERE 
            (ad.searchable_text ILIKE '%' || sub_query || '%'
             OR ad.search_vector @@ plainto_tsquery('english', sub_query))
            AND (p_source_table IS NULL OR ad.source_table = p_source_table)
            AND (p_project_id IS NULL OR ad.project_id = p_project_id)
        ORDER BY rank DESC, ad.updated_at DESC
        LIMIT p_limit_per_query;
        
        -- Increment index for next sub-query
        query_index := query_index + 1;
    END LOOP;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION ai_search_multi_query(text, text, text, integer) TO anon, authenticated, service_role;

-- Test the function (optional - comment out if not needed)
-- SELECT * FROM ai_search_multi_query('gcash or fuel', NULL, NULL, 5);
