from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_URI_SOLFORGE = os.getenv("MONGODB_URI_SOLFORGE")

if not MONGODB_URI:
    raise ValueError("Missing MONGODB_URI in .env")
if not MONGODB_URI_SOLFORGE:
    raise ValueError("Missing MONGODB_URI_SOLFORGE in .env")

client = MongoClient(MONGODB_URI)
clientSOLFORGE = MongoClient(MONGODB_URI_SOLFORGE)

# ✅ Explicitly select the correct DB
db = client["mainnet-beta"]
dbSOLFORGE = clientSOLFORGE["main"]

# Collections - FATCAT
group_subs = db['groupSubscriptions']
projects = db['projects']
raids = db['raids']
users = db['users']

# Collections - SOLFORGE
coins = dbSOLFORGE['coins']
coinstatuses = dbSOLFORGE['coinstatuses']
solforge_users = dbSOLFORGE['users']

