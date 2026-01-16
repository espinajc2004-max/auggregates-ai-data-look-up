-- ========================================
-- CLEANUP TEST DATA FROM AI_DOCUMENTS
-- Generated: 2026-02-15
-- Purpose: Remove test/example data that was inserted via migrations
-- ========================================

-- BACKUP: First, let's see what we're about to delete
-- Run this query first to verify:
-- SELECT file_name, project_name, source_table, COUNT(*) 
-- FROM ai_documents 
-- WHERE file_name IN ('john santos', 'maria reyes', 'pedro cruz', 'ana garcia')
-- GROUP BY file_name, project_name, source_table;

-- DELETE TEST DATA
-- These are example records from migrations, NOT user's real data
DELETE FROM ai_documents
WHERE file_name IN (
  'john santos',
  'maria reyes', 
  'pedro cruz',
  'ana garcia'
);

-- VERIFY CLEANUP
-- After running the delete, verify only real data remains:
-- SELECT file_name, project_name, source_table, COUNT(*) 
-- FROM ai_documents 
-- GROUP BY file_name, project_name, source_table
-- ORDER BY file_name;

-- Expected result after cleanup:
-- francis gays (TEST project) - 7 items
-- QUO-2026-0001 (TEST project) - 4 items
-- Total: 11 items (all real user data)
