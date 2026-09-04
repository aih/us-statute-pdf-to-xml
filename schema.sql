-- PostgreSQL initialization schema

CREATE TABLE IF NOT EXISTS statutes (
    id SERIAL PRIMARY KEY,
    pl_number VARCHAR(50) NOT NULL,
    congress INT,
    law_number INT,
    title VARCHAR(255),
    date_enacted DATE,
    volume INT,
    start_page INT,
    end_page INT,
    pdf_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversions (
    id SERIAL PRIMARY KEY,
    statute_id INT REFERENCES statutes(id),
    module_used VARCHAR(50), -- e.g., 'docling_local'
    uslm_xml_path TEXT,
    doclang_json_path TEXT,
    conversion_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50), -- e.g., 'success', 'failed'
    error_log TEXT
);

CREATE TABLE IF NOT EXISTS benchmarks (
    id SERIAL PRIMARY KEY,
    statute_id INT REFERENCES statutes(id),
    ground_truth_xml_path TEXT,
    generated_xml_path TEXT,
    score DECIMAL(5,2), -- 0 to 100
    vlm_judge_model VARCHAR(100),
    evaluation_details TEXT,
    benchmark_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Unique constraint for statutes
ALTER TABLE statutes ADD CONSTRAINT unique_pl_number UNIQUE (pl_number);
