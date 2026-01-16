-- Migration: Add hybrid search function (semantic + keyword)
-- Purpose: Combine vector similarity search with full-text search
-- Date: 2026-02-13

CREATE OR REPLACE FUNCTION ai_search_hybrid(
    p_query_embedding vector(768),
    p_search_term TEXT,
    p_source_table TEXT DEFAULT NULL,
    p_project_id TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 20,
    p_semantic_weight FLOAT DEFAULT 0.7
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
    semantic_score FLOAT,
    keyword_score FLOAT,
    combined_score FLOAT,
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
        -- Semantic score: cosine similarity (1 - cosine distance)
        -- Higher is better (0 to 1 range)
        (1 - (ad.embedding <=> p_query_embedding))::FLOAT AS semantic_score,
        -- Keyword score: full-text search rank
        -- Higher is better
        ts_rank(ad.search_vector, plainto_tsquery('english', p_search_term))::FLOAT AS keyword_score,
        -- Combined score: weighted average
        -- Default: 70% semantic + 30% keyword
        (
            p_semantic_weight * (1 - (ad.embedding <=> p_query_embedding)) + 
            (1 - p_semantic_weight) * ts_rank(ad.search_vector, plainto_tsquery('english', p_search_term))
        )::FLOAT AS combined_score,
        -- Highlighted matches for keyword search
        ts_headline(
            'english', 
            ad.searchable_text, 
            plainto_tsquery('english', p_search_term), 
            'StartSel=<b>, StopSel=</b>, MaxWords=20, MinWords=5'
        ) AS matched_highlights
    FROM ai_documents ad
    WHERE 
        -- Filter by source table if specified
        (p_source_table IS NULL OR ad.source_table = p_source_table)
        -- Filter by project if specified
        AND (p_project_id IS NULL OR ad.project_id = p_project_id)
        -- Only include documents with embeddings
        AND ad.embedding IS NOT NULL
    ORDER BY combined_score DESC
    LIMIT p_limit;
END;
$$;

-- Add comment for documentation
COMMENT ON FUNCTION ai_search_hybrid IS 'Hybrid search combining semantic similarity (pgvector) with keyword search (full-text). Returns results ranked by weighted combination of both scores.';

-- Example usage:
-- SELECT * FROM ai_search_hybrid(
--     p_query_embedding := (SELECT embedding FROM ai_documents LIMIT 1),
--     p_search_term := 'fuel',
--     p_source_table := 'Expenses',
--     p_limit := 10,
--     p_semantic_weight := 0.7
-- );
