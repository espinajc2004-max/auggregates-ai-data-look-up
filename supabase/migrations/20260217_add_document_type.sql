-- Migration: Add document_type column to ai_documents
-- Date: 2026-02-17
-- Purpose: Distinguish file-level vs row-level documents

-- Add document_type column
ALTER TABLE ai_documents 
ADD COLUMN IF NOT EXISTS document_type TEXT DEFAULT 'row';

-- Add check constraint
ALTER TABLE ai_documents
DROP CONSTRAINT IF EXISTS check_document_type;

ALTER TABLE ai_documents
ADD CONSTRAINT check_document_type 
CHECK (document_type IN ('file', 'row', 'summary'));

-- Create index for filtering
CREATE INDEX IF NOT EXISTS idx_ai_documents_type ON ai_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_ai_documents_org_type ON ai_documents(org_id, document_type);

-- Update existing data based on metadata
UPDATE ai_documents 
SET document_type = 'file' 
WHERE metadata->>'is_file_summary' = 'true'
OR metadata->>'level' = 'file';

UPDATE ai_documents 
SET document_type = 'summary' 
WHERE metadata->>'is_summary' = 'true'
OR metadata->>'level' = 'summary';

-- Comment
COMMENT ON COLUMN ai_documents.document_type IS 'Type of document: file (file metadata), row (data row), summary (aggregated data)';
