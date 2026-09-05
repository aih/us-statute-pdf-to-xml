-- Granule page labels can be lettered (treaties in part B: "B3-B32"); keep the text range and the page count.
ALTER TABLE granules ADD COLUMN IF NOT EXISTS page_range TEXT;
ALTER TABLE granules ADD COLUMN IF NOT EXISTS total_pages INT;
ALTER TABLE granules ADD COLUMN IF NOT EXISTS citation TEXT;
ALTER TABLE granules ADD COLUMN IF NOT EXISTS congress INT;
ALTER TABLE granules ADD COLUMN IF NOT EXISTS era TEXT;
ALTER TABLE granules ADD COLUMN IF NOT EXISTS mods JSONB;
