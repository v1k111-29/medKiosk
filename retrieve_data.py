import sqlite3
import pandas as pd
from pathlib import Path

def retrieve_all_data(db_path):
    print(f"\n{'='*60}")
    print(f"DATABASE: {db_path.name}")
    print(f"{'='*60}")
    
    if not db_path.exists():
        print(f"Error: {db_path} does not exist.")
        return

    try:
        conn = sqlite3.connect(db_path)
        # Get all table names
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall() if row[0] != 'sqlite_sequence']
        
        if not tables:
            print("No data tables found in this database.")
        
        for table in tables:
            print(f"\n--- Table: {table} ---")
            # Using pandas for pretty printing
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            if df.empty:
                print("Table is empty.")
            else:
                # Truncate long strings (like embeddings) for better display
                for col in df.columns:
                    if df[col].dtype == object:
                        df[col] = df[col].apply(lambda x: str(x)[:30] + '...' if len(str(x)) > 33 else x)
                print(df.to_string(index=False))
        
        conn.close()
    except Exception as e:
        print(f"Error accessing {db_path.name}: {e}")

if __name__ == "__main__":
    base_dir = Path(__file__).parent.resolve()
    
    # List of databases to retrieve data from
    databases = [
        base_dir / "patients.db",
        base_dir / "medical.db"
    ]
    
    for db in databases:
        retrieve_all_data(db)
