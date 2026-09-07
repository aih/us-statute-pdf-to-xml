-- Conversions and benchmarks are keyed by granule or package as well as by statute.
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS granule_id TEXT;
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS package_id TEXT;
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS input_path TEXT;
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS input_sha256 TEXT;
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS profile TEXT;
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS page_range TEXT;
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS pages INT;
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS seconds REAL;
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS xsd_valid BOOLEAN;
CREATE UNIQUE INDEX IF NOT EXISTS conversions_unit ON conversions (COALESCE(granule_id, package_id), COALESCE(page_range, ''), module_used);

ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS granule_id TEXT;
ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS package_id TEXT;
ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS era TEXT;
ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS cer REAL;
ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS wer REAL;
ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS metrics JSONB;
ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS judge JSONB;
ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS judge_cost_usd REAL;
ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS run_id TEXT;
