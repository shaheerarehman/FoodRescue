import uuid
from datetime import datetime, timezone

import requests

from config import GOOGLE_MAPS_API_KEY
from models import DonationCreate
from repository import DonationRepository
from states import DonationStateFactory


class GeocodingService:
    """Keeps third-party Google Geocoding integration separate from core application logic."""

    def geocode(self, address: str):
        if not GOOGLE_MAPS_API_KEY:
            return None, None
        response = requests.get(
            'https://maps.googleapis.com/maps/api/geocode/json',
            params={'address': address, 'key': GOOGLE_MAPS_API_KEY},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        if data.get('status') != 'OK' or not data.get('results'):
            return None, None
        location = data['results'][0]['geometry']['location']
        return str(location['lat']), str(location['lng'])


class DonationService:
    """Shared core application logic used by both HTML and REST interfaces."""

    def __init__(self, repo: DonationRepository, geo: GeocodingService):
        self.repo = repo
        self.geo = geo

    def create_donation(self, donation: DonationCreate):
        lat, lng = self.geo.geocode(donation.pickup_address)
        item = {
            'donation_id': str(uuid.uuid4()),
            'food_type': donation.food_type,
            'quantity': donation.quantity,
            'pickup_address': donation.pickup_address,
            'pickup_deadline': donation.pickup_deadline,
            'description': donation.description,
            'status': 'AVAILABLE',
            'reserved_by': '',
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        if lat is not None:
            item.update(latitude=lat, longitude=lng)
        return self.repo.create(item)

    def expire_past_deadline_donations(self):
        items = self.repo.list_all()
        now = datetime.now()
        for item in items:
            if item.get('status') != 'AVAILABLE':
                continue
            try:
                deadline = datetime.fromisoformat(item['pickup_deadline'])
            except (ValueError, TypeError, KeyError):
                continue
            if deadline < now:
                current_state = DonationStateFactory.create_state(item['status'])
                new_state = current_state.expire()
                try:
                    self.repo.update_status(item['donation_id'], item['status'], new_state.name)
                except ValueError:
                    pass

    def get_available_donations(self):
        self.expire_past_deadline_donations()
        return self.repo.list_available()

    def get_all_donations(self):
        return self.repo.list_all()

    def reserve_donation(self, donation_id: str, charity_name: str):
        item = self.repo.get(donation_id)
        if not item:
            raise ValueError('Donation not found')
        DonationStateFactory.create_state(item['status']).reserve()
        return self.repo.reserve_atomically(donation_id, charity_name)

    def complete_donation(self, donation_id: str):
        item = self.repo.get(donation_id)
        if not item:
            raise ValueError('Donation not found')
        current_state = DonationStateFactory.create_state(item['status'])
        new_state = current_state.complete()
        return self.repo.update_status(donation_id, item['status'], new_state.name)

    def expire_donation(self, donation_id: str):
        item = self.repo.get(donation_id)
        if not item:
            raise ValueError('Donation not found')
        current_state = DonationStateFactory.create_state(item['status'])
        new_state = current_state.expire()
        return self.repo.update_status(donation_id, item['status'], new_state.name)


def service():
    return DonationService(DonationRepository(), GeocodingService())
