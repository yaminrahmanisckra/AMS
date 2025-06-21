#!/usr/bin/env python3
"""
Database initialization script for Academic Management System
This script creates sample data for testing the application
"""

from app import app, db
# Import all models from all blueprints
from blueprints.class_management.models import *
from blueprints.result_management.models import *

with app.app_context():
    print("Dropping all tables...")
    db.drop_all()
    print("Creating all tables...")
    db.create_all()
    print("Database has been reset.") 