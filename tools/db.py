from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")


if not MONGODB_URI:
    raise ValueError("Missing MONGODB_URI in .env")


client = MongoClient(MONGODB_URI)


# ✅ Explicitly select the correct DB
db = client["mainnet-beta"]


# Collections - FATCAT
group_subs = db['groupSubscriptions']
projects = db['projects']
raids = db['raids']
users = db['users']



