-- GovInfo packages (one row per STATUTE volume or PLAW law) and granules (one row per law,
-- resolution, proclamation, or treaty inside a STATUTE volume).

CREATE TABLE IF NOT EXISTS packages (
    package_id      TEXT PRIMARY KEY,           -- e.g. STATUTE-64, PLAW-118publ5
    collection      TEXT NOT NULL,              -- STATUTE or PLAW
    volume          INT,
    congress        INT,
    session         INT,
    date_issued     DATE,
    pages           INT,
    title           TEXT,
    scanned         BOOLEAN,                    -- STATUTE volumes 1-116 are scanned images
    pdf_url         TEXT,
    pdf_bytes       BIGINT,                     -- Content-Length reported by GovInfo
    pdf_sha256      TEXT,
    pdf_local_path  TEXT,
    pdf_status      TEXT NOT NULL DEFAULT 'pending',  -- pending, downloaded, uploaded, verified
    xml_url         TEXT,
    xml_bytes       BIGINT,
    xml_sha256      TEXT,
    xml_local_path  TEXT,
    xml_status      TEXT NOT NULL DEFAULT 'pending',
    hub_commit      TEXT,
    hub_pdf_path    TEXT,
    hub_xml_path    TEXT,
    summary         JSONB,                      -- full /summary response
    downloaded_at   TIMESTAMPTZ,
    uploaded_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS packages_collection_volume ON packages (collection, volume);

CREATE TABLE IF NOT EXISTS granules (
    granule_id      TEXT PRIMARY KEY,           -- e.g. STATUTE-64-Pg371
    package_id      TEXT NOT NULL REFERENCES packages(package_id),
    granule_class   TEXT,                       -- PUBLICLAW, PRIVATELAW, PROCLAMATION, TREATY, ...
    title           TEXT,
    number          TEXT,                       -- law/proclamation/treaty number when present
    date_issued     DATE,
    page_start      INT,                        -- pagePosition from the granule summary
    page_end        INT,
    pdf_url         TEXT,
    mods_url        TEXT,
    pdf_bytes       BIGINT,
    pdf_sha256      TEXT,
    pdf_local_path  TEXT,
    mods_local_path TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    summary         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS granules_package ON granules (package_id);
