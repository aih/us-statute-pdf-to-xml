-- GovInfo titles exceed 255 characters.
ALTER TABLE statutes ALTER COLUMN title TYPE TEXT;
