import os
from dotenv import load_dotenv

load_dotenv()

TABLE_NAME = os.getenv('DYNAMODB_TABLE', 'FoodRescueDonations')
AWS_REGION = os.getenv('AWS_REGION', 'ca-central-1')
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
