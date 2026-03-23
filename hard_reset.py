import os
import sqlite3
import glob
import logging
from db import DB_PATH, DATA_DIR
import setup_database

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def hard_reset():
    logging.info("Starting LINARES System Reset (Movie Data only)...")
    
    # 1. Clear movies table
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            logging.info("Deleting all movies from cache...")
            cursor.execute("DELETE FROM movies")
            conn.commit()
            conn.close()
            logging.info("Movie cache cleared successfully.")
        except Exception as e:
            logging.error(f"Error clearing movies table: {e}")
    
    # 2. Delete models
    logging.info("Deleting old CatBoost models...")
    model_files = glob.glob(os.path.join(DATA_DIR, "model_*.cbm"))
    for f in model_files:
        try:
            os.remove(f)
            logging.info(f"Removed model: {os.path.basename(f)}")
        except Exception as e:
            logging.error(f"Error removing {f}: {e}")
            
    # 3. Re-run setup_database
    logging.info("Re-running setup_database to populate fresh movies...")
    setup_database.download_and_process()
    
    logging.info("System Reset Complete! users and ratings were PRESERVED.")

if __name__ == "__main__":
    hard_reset()
