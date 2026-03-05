import os
from dotenv import load_dotenv
from hubspot import HubSpot

# Load environment variables from .env
load_dotenv()

HUBSPOT_PRIVATE_APP_TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")

if not HUBSPOT_PRIVATE_APP_TOKEN:
    raise ValueError("HubSpot token not found. Check your .env file.")

# Create HubSpot client
client = HubSpot(access_token=HUBSPOT_PRIVATE_APP_TOKEN)

def get_hubspot_client():
    return client