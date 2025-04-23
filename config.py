# config.py (excluded via .gitignore)
import os

MPESA_CREDENTIALS = {
    "consumer_key": os.getenv("MPESA_CONSUMER_KEY"),
    "consumer_secret": os.getenv("MPESA_CONSUMER_SECRET"),
}