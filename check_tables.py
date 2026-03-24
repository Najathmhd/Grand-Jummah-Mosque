import os
from supabase import create_client, Client
from dotenv import load_dotenv
import json

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

print("--- SUPABASE DIAGNOSTIC TOOL ---")
print(f"URL: {url}")

def check_table(table_name):
    try:
        # Check if we can even access the table
        res = supabase.table(table_name).select("count", count="exact").limit(0).execute()
        print(f"[OK] Table '{table_name}' exists.")
        return True
    except Exception as e:
        print(f"[FAIL] Table '{table_name}' NOT FOUND. (Error: {e})")
        return False

print("\nChecking required tables...")
tables = ["members", "events", "distributions", "admins"]
missing = []

for t in tables:
    if not check_table(t):
        missing.append(t)

if missing:
    print("\n!!! ACTION REQUIRED !!!")
    print(f"The following tables are missing: {', '.join(missing)}")
    print("\nYou MUST run the SQL code in the Supabase Dashboard.")
    print("Go to: https://supabase.com/dashboard/project/ieacenzsuqywqzllqgcm/sql/new")
    print("\nCopy the content from your 'supabase_schema.sql' file and click 'RUN'.")
else:
    print("\n[SUCCESS] All tables are present! You can now run 'python app.py'.")
