import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

try:
    print(f"Connecting to: {url}")
    # Try to fetch something from the members table
    response = supabase.table('members').select("id").limit(1).execute()
    print("Successfully connected and found 'members' table.")
except Exception as e:
    print("\n[ERROR] Could not find 'members' table.")
    print(f"Error details: {e}")
    print("\n[ACTION REQUIRED]:")
    print("1. Log in to https://supabase.com")
    print("2. Open your project: ieacenzsuqywqzllqgcm")
    print("3. Go to the 'SQL Editor' (on the left sidebar)")
    print("4. Copy the content of 'supabase_schema.sql' and PASTE it into a new query.")
    print("5. Click the 'RUN' button at the bottom right.")
