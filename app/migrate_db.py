"""
Database migration script to add new columns for asset management features.
Run this once to update your existing database schema.
"""
import sqlite3
from pathlib import Path

# Database file path (adjust if your database is in a different location)
DB_PATH = Path("app.db")

if not DB_PATH.exists():
    print(f"Database file {DB_PATH} not found. It will be created automatically on next app start.")
    exit(0)

print(f"Connecting to database: {DB_PATH}")
conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

# Get current table schema
cursor.execute("PRAGMA table_info(campaign)")
campaign_columns = [row[1] for row in cursor.fetchall()]

cursor.execute("PRAGMA table_info(generatedimage)")
image_columns = [row[1] for row in cursor.fetchall()]

print(f"Current campaign columns: {campaign_columns}")
print(f"Current generatedimage columns: {image_columns}")

# Add missing columns to campaign table
if "original_product_image_url" not in campaign_columns:
    print("Adding 'original_product_image_url' column to campaign table...")
    cursor.execute("ALTER TABLE campaign ADD COLUMN original_product_image_url TEXT")
    print("✓ Added original_product_image_url")

# Add missing columns to generatedimage table
missing_image_columns = {
    "original_image_url": "TEXT",
    "variation_number": "INTEGER DEFAULT 0",
    "is_selected": "INTEGER DEFAULT 0",  # SQLite uses INTEGER for booleans
    "tags": "TEXT",  # JSON stored as TEXT in SQLite
    "collection": "TEXT",
}

for col_name, col_type in missing_image_columns.items():
    if col_name not in image_columns:
        print(f"Adding '{col_name}' column to generatedimage table...")
        cursor.execute(f"ALTER TABLE generatedimage ADD COLUMN {col_name} {col_type}")
        print(f"✓ Added {col_name}")

# Create indexes for better performance
print("\nCreating indexes...")
try:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_generatedimage_variation_number ON generatedimage(variation_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_generatedimage_is_selected ON generatedimage(is_selected)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_generatedimage_collection ON generatedimage(collection)")
    print("✓ Indexes created")
except sqlite3.OperationalError as e:
    print(f"Note: Some indexes may already exist: {e}")

conn.commit()
conn.close()

print("\n✅ Database migration completed successfully!")
print("You can now restart your application.")

