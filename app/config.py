# config.py
import os

class Config:
    SECRET_KEY = os.urandom(24)
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:postgressqlGhada@localhost:5432/smartChaine2'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
