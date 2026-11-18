from config import GEOCODING_PROVIDER, GOOGLE_MAPS_API_KEY
from geocoding_providers import GoogleGeocodingProvider, SimulatedGeocodingProvider
from repository import DonationRepository
from services import DonationService


def configured_provider():
    if GEOCODING_PROVIDER == 'google':
        return GoogleGeocodingProvider(GOOGLE_MAPS_API_KEY)
    if GEOCODING_PROVIDER == 'simulated':
        return SimulatedGeocodingProvider()
    raise ValueError('GEOCODING_PROVIDER must be google or simulated')


provider = configured_provider()


def service():
    return DonationService(DonationRepository(), provider)
