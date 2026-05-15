#!/usr/bin/env python
"""Initialize database tables"""
from db.database import Base, engine
from db import models

# Create all tables
Base.metadata.create_all(bind=engine)
print("✅ Database tables created successfully!")
