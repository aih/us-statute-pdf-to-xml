-- Builder accounting per conversion (WP8): warning count and log, Docling text characters, characters kept
-- in the generated document. `module_used` now carries the profile name (scanned, digital, tesseract:psm6, ...).
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS warnings INT;
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS warning_log TEXT;
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS docling_chars INT;
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS body_chars INT;
ALTER TABLE conversions ADD COLUMN IF NOT EXISTS kept_chars INT;

ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS profile TEXT;
ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS tier TEXT;
