-- =============================================================================
-- Real-Time Vocabulary Sync Triggers
-- =============================================================================
-- Creates PostgreSQL triggers on all vocabulary tables to automatically
-- notify the AI system when data changes (INSERT/UPDATE/DELETE).
-- The bridge service listens for these notifications and refreshes the
-- Redis vocabulary cache within 1-2 seconds.
-- =============================================================================

-- 1. Create the trigger function with error handling
CREATE OR REPLACE FUNCTION notify_vocabulary_change()
RETURNS TRIGGER AS $$
BEGIN
    BEGIN
        -- Publish notification with table name as payload
        PERFORM pg_notify('vocabulary_changed', TG_TABLE_NAME);
    EXCEPTION WHEN OTHERS THEN
        -- Log error but don't block the original database operation
        RAISE WARNING 'Failed to notify vocabulary change for table %: %', TG_TABLE_NAME, SQLERRM;
    END;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. Create triggers on all five vocabulary tables
-- Using FOR EACH STATEMENT to avoid duplicate notifications on bulk operations

-- Project table trigger
DROP TRIGGER IF EXISTS vocabulary_change_trigger ON "Project";
CREATE TRIGGER vocabulary_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON "Project"
FOR EACH STATEMENT
EXECUTE FUNCTION notify_vocabulary_change();

-- Expenses table trigger
DROP TRIGGER IF EXISTS vocabulary_change_trigger ON "Expenses";
CREATE TRIGGER vocabulary_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON "Expenses"
FOR EACH STATEMENT
EXECUTE FUNCTION notify_vocabulary_change();

-- CashFlow table trigger
DROP TRIGGER IF EXISTS vocabulary_change_trigger ON "CashFlow";
CREATE TRIGGER vocabulary_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON "CashFlow"
FOR EACH STATEMENT
EXECUTE FUNCTION notify_vocabulary_change();

-- ExpensesColumn table trigger
DROP TRIGGER IF EXISTS vocabulary_change_trigger ON "ExpensesColumn";
CREATE TRIGGER vocabulary_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON "ExpensesColumn"
FOR EACH STATEMENT
EXECUTE FUNCTION notify_vocabulary_change();

-- CashFlowColumn table trigger
DROP TRIGGER IF EXISTS vocabulary_change_trigger ON "CashFlowColumn";
CREATE TRIGGER vocabulary_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON "CashFlowColumn"
FOR EACH STATEMENT
EXECUTE FUNCTION notify_vocabulary_change();
