import os
import psycopg2
from psycopg2.extras import DictCursor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_connection():
    db_url = os.getenv("POSTGRES_URL", "postgresql://postgres:password@localhost:5432/statutes")
    return psycopg2.connect(db_url, cursor_factory=DictCursor)

def init_db():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            with open("schema.sql", "r") as f:
                cur.execute(f.read())
        conn.commit()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize db: {e}")
        conn.rollback()
    finally:
        conn.close()

def insert_statute(pl_number, congress, law_number, title, date_enacted, volume, start_page, end_page, pdf_path):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO statutes (pl_number, congress, law_number, title, date_enacted, volume, start_page, end_page, pdf_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (pl_number) DO NOTHING
                RETURNING id;
            """, (pl_number, congress, law_number, title, date_enacted, volume, start_page, end_page, pdf_path))
            result = cur.fetchone()
            conn.commit()
            return result['id'] if result else None
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
