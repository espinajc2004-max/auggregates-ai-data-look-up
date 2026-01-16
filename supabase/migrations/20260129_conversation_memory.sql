-- ============================================
-- 20260129_conversation_memory.sql
-- Database-Based Long-Term Conversation Memory
-- ============================================

-- 1. Create conversation_turns table
CREATE TABLE IF NOT EXISTS conversation_turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    user_id UUID NOT NULL,
    turn_number INTEGER NOT NULL,
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Constraints
    CONSTRAINT unique_session_turn UNIQUE (session_id, turn_number),
    CONSTRAINT positive_turn_number CHECK (turn_number > 0),
    CONSTRAINT non_empty_query CHECK (LENGTH(TRIM(query_text)) > 0),
    CONSTRAINT non_empty_response CHECK (LENGTH(TRIM(response_text)) > 0)
);

-- 2. Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_session_id ON conversation_turns(session_id);
CREATE INDEX IF NOT EXISTS idx_created_at ON conversation_turns(created_at);
CREATE INDEX IF NOT EXISTS idx_user_sessions ON conversation_turns(user_id, session_id);

-- 3. Create index for cleanup queries (regular index, partial index not needed)
CREATE INDEX IF NOT EXISTS idx_cleanup ON conversation_turns(created_at);

-- 4. Create function to get next turn number for a session
CREATE OR REPLACE FUNCTION get_next_turn_number(p_session_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    next_turn INTEGER;
BEGIN
    SELECT COALESCE(MAX(turn_number), 0) + 1
    INTO next_turn
    FROM conversation_turns
    WHERE session_id = p_session_id;
    
    RETURN next_turn;
END;
$$;

-- 4b. Create function to insert conversation turn
CREATE OR REPLACE FUNCTION insert_conversation_turn(
    p_session_id UUID,
    p_user_id UUID,
    p_turn_number INTEGER,
    p_query_text TEXT,
    p_response_text TEXT,
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id UUID,
    session_id UUID,
    user_id UUID,
    turn_number INTEGER,
    query_text TEXT,
    response_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    INSERT INTO conversation_turns (session_id, user_id, turn_number, query_text, response_text, metadata)
    VALUES (p_session_id, p_user_id, p_turn_number, p_query_text, p_response_text, p_metadata)
    RETURNING *;
END;
$$;

-- 5. Create function to cleanup old conversations
CREATE OR REPLACE FUNCTION cleanup_old_conversations()
RETURNS TABLE (
    sessions_deleted BIGINT,
    turns_deleted BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_sessions BIGINT;
    deleted_turns BIGINT;
BEGIN
    -- Count sessions to be deleted
    SELECT COUNT(DISTINCT session_id)
    INTO deleted_sessions
    FROM conversation_turns
    WHERE created_at < NOW() - INTERVAL '24 hours';
    
    -- Delete old turns (cascades by session)
    WITH deleted AS (
        DELETE FROM conversation_turns
        WHERE created_at < NOW() - INTERVAL '24 hours'
        RETURNING *
    )
    SELECT COUNT(*) INTO deleted_turns FROM deleted;
    
    RETURN QUERY SELECT deleted_sessions, deleted_turns;
END;
$$;

-- 6. Permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON conversation_turns TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION get_next_turn_number(UUID) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION insert_conversation_turn(UUID, UUID, INTEGER, TEXT, TEXT, JSONB) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION cleanup_old_conversations() TO anon, authenticated, service_role;

-- 7. Row Level Security (RLS)
ALTER TABLE conversation_turns ENABLE ROW LEVEL SECURITY;

-- Allow users to read their own conversations
CREATE POLICY "Users can read own conversations" 
ON conversation_turns FOR SELECT 
USING (auth.uid() = user_id OR auth.uid() IS NULL);

-- Allow users to insert their own conversations
CREATE POLICY "Users can insert own conversations" 
ON conversation_turns FOR INSERT 
WITH CHECK (auth.uid() = user_id OR auth.uid() IS NULL);

-- Allow users to delete their own conversations
CREATE POLICY "Users can delete own conversations" 
ON conversation_turns FOR DELETE 
USING (auth.uid() = user_id OR auth.uid() IS NULL);

-- Allow service role full access
CREATE POLICY "Service role has full access" 
ON conversation_turns FOR ALL 
USING (auth.role() = 'service_role');

-- 8. Add comment for documentation
COMMENT ON TABLE conversation_turns IS 'Stores conversation history for long-term memory with automatic 24-hour cleanup';
COMMENT ON COLUMN conversation_turns.session_id IS 'Unique identifier for a conversation session';
COMMENT ON COLUMN conversation_turns.turn_number IS 'Sequential turn number within a session (1, 2, 3, ...)';
COMMENT ON COLUMN conversation_turns.metadata IS 'Extensible JSON field for additional context (e.g., confidence scores, references)';
