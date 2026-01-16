-- Migration: Add vocabulary_cache table
-- Date: 2026-02-17
-- Purpose: Cache frequently accessed vocabulary to reduce DB load

-- Create vocabulary_cache table
CREATE TABLE IF NOT EXISTS vocabulary_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    cache_key TEXT NOT NULL,  -- 'categories', 'projects', 'files'
    cache_value JSONB NOT NULL,  -- Cached data
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(org_id, cache_key)
);

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_vocabulary_cache_lookup 
ON vocabulary_cache(org_id, cache_key, expires_at);

-- Function to cleanup expired cache
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM vocabulary_cache WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to get top categories
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

-- Comment
COMMENT ON TABLE vocabulary_cache IS 'Caches vocabulary (categories, projects, files) per org with TTL';
COMMENT ON FUNCTION get_top_categories IS 'Returns top N categories for an org ordered by frequency';
