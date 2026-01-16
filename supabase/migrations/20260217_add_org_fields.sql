-- Migration: Add org_fields table for dynamic column tracking
-- Date: 2026-02-17
-- Purpose: Enable support for ANY custom column at runtime

-- Create org_fields table
CREATE TABLE IF NOT EXISTS org_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    table_name TEXT NOT NULL,  -- 'Expenses', 'CashFlow', 'Inventory'
    field_name TEXT NOT NULL,  -- 'supplier', 'invoice_no', 'tax', 'vat'
    field_type TEXT NOT NULL,  -- 'text', 'numeric', 'date', 'currency'
    aliases TEXT[],  -- ['vendor', 'proveedor', 'supplier']
    is_custom BOOLEAN DEFAULT true,
    is_visible BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(org_id, table_name, field_name)
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_org_fields_lookup ON org_fields(org_id, table_name);
CREATE INDEX IF NOT EXISTS idx_org_fields_name ON org_fields(field_name);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS update_org_fields_updated_at ON org_fields;
CREATE TRIGGER update_org_fields_updated_at
    BEFORE UPDATE ON org_fields
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert default/global fields for Expenses
INSERT INTO org_fields (org_id, table_name, field_name, field_type, is_custom, aliases)
SELECT 
    o.id as org_id,
    'Expenses' as table_name,
    field_name,
    field_type,
    false as is_custom,
    aliases
FROM (VALUES
    ('category', 'text', ARRAY['type', 'classification']),
    ('amount', 'numeric', ARRAY['cost', 'price', 'value']),
    ('date', 'date', ARRAY['created_date', 'transaction_date']),
    ('method', 'text', ARRAY['payment_method', 'mode']),
    ('file_name', 'text', ARRAY['file', 'document']),
    ('project', 'text', ARRAY['project_name']),
    ('description', 'text', ARRAY['notes', 'details'])
) AS fields(field_name, field_type, aliases)
CROSS JOIN (SELECT DISTINCT org_id as id FROM ai_documents WHERE org_id IS NOT NULL) o
ON CONFLICT (org_id, table_name, field_name) DO NOTHING;

-- Insert default/global fields for CashFlow
INSERT INTO org_fields (org_id, table_name, field_name, field_type, is_custom, aliases)
SELECT 
    o.id as org_id,
    'CashFlow' as table_name,
    field_name,
    field_type,
    false as is_custom,
    aliases
FROM (VALUES
    ('category', 'text', ARRAY['type', 'classification']),
    ('amount', 'numeric', ARRAY['cost', 'price', 'value']),
    ('date', 'date', ARRAY['created_date', 'transaction_date']),
    ('method', 'text', ARRAY['payment_method', 'mode']),
    ('file_name', 'text', ARRAY['file', 'document']),
    ('project', 'text', ARRAY['project_name']),
    ('description', 'text', ARRAY['notes', 'details'])
) AS fields(field_name, field_type, aliases)
CROSS JOIN (SELECT DISTINCT org_id as id FROM ai_documents WHERE org_id IS NOT NULL) o
ON CONFLICT (org_id, table_name, field_name) DO NOTHING;

-- Comment
COMMENT ON TABLE org_fields IS 'Tracks all fields (global + custom) per org and table. Enables dynamic column support.';
