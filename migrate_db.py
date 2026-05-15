"""
Database migration script to add new columns to existing tables
Run this to update your existing database with new columns
"""

from sqlalchemy import text
from db.database import engine

def run_migration():
    """Add new columns to existing tables"""
    
    # STEP 1: Create new tables first (topviews must exist before trees.topview_id FK)
    create_tables = [
        ("topviews", """
        CREATE TABLE IF NOT EXISTS topviews (
            id SERIAL PRIMARY KEY,
            survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
            topview_order VARCHAR NOT NULL,
            image_path VARCHAR,
            total_trees INTEGER,
            healthy_count INTEGER,
            unhealthy_count INTEGER,
            health_score FLOAT,
            dominant_disease VARCHAR,
            dashboard_snapshot JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(survey_id, topview_order)
        );
        """),
        ("topview_trees", """
        CREATE TABLE IF NOT EXISTS topview_trees (
            id SERIAL PRIMARY KEY,
            topview_id INTEGER NOT NULL REFERENCES topviews(id) ON DELETE CASCADE,
            tree_index VARCHAR NOT NULL,
            health VARCHAR,
            weighted_score FLOAT,
            dashboard_json JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(topview_id, tree_index)
        );
        """),
        ("analysis_history", """
        CREATE TABLE IF NOT EXISTS analysis_history (
            id SERIAL PRIMARY KEY,
            farmer_id INTEGER REFERENCES farmers(id) ON DELETE SET NULL,
            image_path VARCHAR NOT NULL,
            analysis_type VARCHAR DEFAULT 'image',
            score FLOAT NOT NULL,
            label VARCHAR NOT NULL,
            part VARCHAR,
            status VARCHAR,
            part_confidence FLOAT,
            status_confidence FLOAT,
            recommendation_summary TEXT,
            result_data JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """),
    ]
    
    # STEP 2: Alter existing tables to add new columns
    migrations = [
        # Farmer table - add created_at
        ("farmers", "created_at", """
        ALTER TABLE farmers 
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
        """),
        
        # Survey table - add topview_image_path, extra_data, created_at
        ("surveys", "topview_image_path", """
        ALTER TABLE surveys 
        ADD COLUMN IF NOT EXISTS topview_image_path VARCHAR;
        """),
        ("surveys", "extra_data", """
        ALTER TABLE surveys 
        ADD COLUMN IF NOT EXISTS extra_data JSON DEFAULT '{}';
        """),
        ("surveys", "created_at", """
        ALTER TABLE surveys 
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
        """),
        
        # Tree table - add all new columns
        ("trees", "topview_id", """
        ALTER TABLE trees 
        ADD COLUMN IF NOT EXISTS topview_id INTEGER REFERENCES topviews(id);
        """),
        ("trees", "final_status", """
        ALTER TABLE trees 
        ADD COLUMN IF NOT EXISTS final_status VARCHAR;
        """),
        ("trees", "final_health_percentage", """
        ALTER TABLE trees 
        ADD COLUMN IF NOT EXISTS final_health_percentage FLOAT;
        """),
        ("trees", "critical_alert", """
        ALTER TABLE trees 
        ADD COLUMN IF NOT EXISTS critical_alert BOOLEAN DEFAULT FALSE;
        """),
        ("trees", "cx", """
        ALTER TABLE trees 
        ADD COLUMN IF NOT EXISTS cx INTEGER;
        """),
        ("trees", "cy", """
        ALTER TABLE trees 
        ADD COLUMN IF NOT EXISTS cy INTEGER;
        """),
        ("trees", "dashboard_data", """
        ALTER TABLE trees 
        ADD COLUMN IF NOT EXISTS dashboard_data JSON;
        """),
        ("trees", "extra_data", """
        ALTER TABLE trees 
        ADD COLUMN IF NOT EXISTS extra_data JSON DEFAULT '{}';
        """),
        ("trees", "created_at", """
        ALTER TABLE trees 
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
        """),
        
        # TreePart table - add status, extra, timestamp
        ("tree_parts", "status", """
        ALTER TABLE tree_parts 
        ADD COLUMN IF NOT EXISTS status VARCHAR;
        """),
        ("tree_parts", "extra", """
        ALTER TABLE tree_parts 
        ADD COLUMN IF NOT EXISTS extra JSON DEFAULT '{}';
        """),
        ("tree_parts", "timestamp", """
        ALTER TABLE tree_parts 
        ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
        """),
    ]

    print("[*] Running database migration...")
    print("=" * 60)
    
    with engine.connect() as conn:
        # STEP 1: Create new tables FIRST (order matters for FK references)
        print("\n[STEP 1] Creating new tables...")
        for table_name, sql in create_tables:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"  [OK] Created table (if not exists): {table_name}")
            except Exception as e:
                conn.rollback()
                print(f"  [!!] Create table {table_name} failed: {e}")
        
        # STEP 2: Add new columns to existing tables
        print("\n[STEP 2] Adding columns to existing tables...")
        for i, (table, column, sql) in enumerate(migrations, 1):
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"  [OK] {i}. Added {column} to {table}")
            except Exception as e:
                conn.rollback()
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"  [--] {i}. {column} already exists in {table}")
                else:
                    print(f"  [!!] {i}. Failed to add {column} to {table}: {e}")

    print("\n" + "=" * 60)
    print("[OK] Migration completed!")
    print("\nYou can now restart your server and test the API endpoints.")

if __name__ == "__main__":
    run_migration()
