import uuid
from datetime import datetime, timedelta, timezone

from geocoding import GeocodingProvider, GeocodingUnavailable
from models import DonationCreate
from repository import DonationRepository, WriteConflict
from states import DonationStateFactory


RESERVATION_PERIOD = timedelta(hours=2)
GEOCODING_RETRY_DELAY = timedelta(minutes=5)
ACTIVE_STATUSES = ('AVAILABLE', 'RESERVED')


def parse_timestamp(value):
    try:
        # Existing offset-free pickup deadlines use the host's local timezone.
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


class DonationService:
    """Shared core application logic used by both HTML and REST interfaces."""

    def __init__(self, repo: DonationRepository, geo: GeocodingProvider,
                 now=lambda: datetime.now(timezone.utc)):
        self.repo = repo
        self.geo = geo
        self.now = now

    def lookup_location(self, address):
        try:
            location = self.geo.geocode(address)
        except GeocodingUnavailable:
            return {'geocoding_status': 'PENDING'}
        if location is None:
            return {'geocoding_status': 'NO_MATCH'}
        return {
            'geocoding_status': 'RESOLVED',
            'latitude': location.latitude,
            'longitude': location.longitude,
            'coordinates_approximate': location.approximate,
        }

    def create_donation(self, donation: DonationCreate):
        item = {
            'donation_id': str(uuid.uuid4()),
            'food_type': donation.food_type,
            'quantity': donation.quantity,
            'pickup_address': donation.pickup_address,
            'pickup_deadline': donation.pickup_deadline,
            'description': donation.description,
            'status': 'AVAILABLE',
            'reserved_by': '',
            'created_at': self.now().isoformat(),
        }
        item.update(self.lookup_location(donation.pickup_address))
        if item['geocoding_status'] == 'PENDING':
            item['geocoding_retry_at'] = (self.now() + GEOCODING_RETRY_DELAY).isoformat()
        return self.repo.create(item)

    def expire_due_donations(self, *, include_reservations=True):
        now = self.now()
        for item in self.repo.scan_items():
            status = item.get('status')
            deadline = parse_timestamp(item.get('pickup_deadline'))
            pickup_ended = deadline is not None and deadline <= now
            try:
                if status == 'AVAILABLE' and pickup_ended:
                    self.repo.update_status(item, 'EXPIRED')
                elif status == 'RESERVED' and include_reservations:
                    expires = parse_timestamp(item.get('reservation_expires_at'))
                    if pickup_ended:
                        self.repo.update_status(item, 'EXPIRED', release=True)
                    elif expires is None:
                        self.repo.start_legacy_reservation_timer(item, now, now + RESERVATION_PERIOD)
                    elif expires <= now:
                        # A malformed legacy deadline cannot establish that pickup is still safe.
                        self.repo.update_status(item, 'AVAILABLE' if deadline else 'EXPIRED', release=True)
            except WriteConflict:
                continue

    def retry_geocoding(self, limit=8):
        now = self.now()
        candidates = []
        for item in self.repo.scan_items():
            if item.get('status') not in ACTIVE_STATUSES or not item.get('pickup_address'):
                continue
            if item.get('geocoding_status') != 'PENDING':
                continue
            deadline = parse_timestamp(item.get('pickup_deadline'))
            if deadline is not None and deadline <= now:
                continue
            if item.get('geocoding_retry_at', '') <= now.isoformat():
                candidates.append(item)

        candidates.sort(key=lambda item: item.get('geocoding_retry_at', ''))
        attempts = 0
        for item in candidates:
            if attempts >= limit:
                break
            try:
                retry_at = (self.now() + GEOCODING_RETRY_DELAY).isoformat()
                self.repo.claim_geocoding_retry(item, retry_at)
                attempts += 1
                result = self.lookup_location(item['pickup_address'])
                if result['geocoding_status'] != 'PENDING':
                    self.repo.finish_geocoding_retry(item, retry_at, result)
            except WriteConflict:
                continue

    def get_available_donations(self):
        self.expire_due_donations(include_reservations=False)
        return self.repo.list_available()

    def get_all_donations(self):
        return self.repo.list_all()

    def get_donation(self, donation_id):
        item = self.repo.get(donation_id)
        if not item:
            raise ValueError('Donation not found')
        return item

    def reserve_donation(self, donation_id: str, charity_name: str):
        item = self.get_donation(donation_id)
        DonationStateFactory.create_state(item['status']).reserve()
        now = self.now()
        deadline = parse_timestamp(item.get('pickup_deadline'))
        if deadline is not None and deadline <= now:
            raise ValueError('Pickup deadline has passed')
        return self.repo.reserve_atomically(item, charity_name, now, now + RESERVATION_PERIOD)

    def complete_donation(self, donation_id: str):
        item = self.get_donation(donation_id)
        new_state = DonationStateFactory.create_state(item['status']).complete()
        now = self.now()
        expires = parse_timestamp(item.get('reservation_expires_at'))
        deadline = parse_timestamp(item.get('pickup_deadline'))
        if (expires and expires <= now) or (deadline and deadline <= now):
            raise ValueError('Pickup window has passed')
        return self.repo.update_status(item, new_state.name)

    def expire_donation(self, donation_id: str):
        item = self.get_donation(donation_id)
        new_state = DonationStateFactory.create_state(item['status']).expire()
        return self.repo.update_status(item, new_state.name)
