import hashlib

import requests

from geocoding import Coordinates, GeocodingUnavailable


class GoogleGeocodingProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def geocode(self, address: str):
        if not self.api_key:
            raise GeocodingUnavailable()
        try:
            response = requests.get(
                'https://maps.googleapis.com/maps/api/geocode/json',
                params={'address': address, 'key': self.api_key},
                timeout=(2, 3),
                allow_redirects=False,
            )
            response.raise_for_status()
            data = response.json()
            if data['status'] == 'ZERO_RESULTS':
                return None
            if data['status'] != 'OK':
                raise GeocodingUnavailable()
            location = data['results'][0]['geometry']['location']
            lat, lng = float(location['lat']), float(location['lng'])
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError('Invalid coordinate')
            return Coordinates(str(lat), str(lng))
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError, OverflowError):
            # Request errors can contain the URL, including the API key.
            raise GeocodingUnavailable() from None


class SimulatedGeocodingProvider:
    def geocode(self, address: str):
        digest = hashlib.sha256(address.strip().casefold().encode()).digest()
        latitude = 43.25 + (digest[0] / 255 - 0.5) * 0.06
        longitude = -79.87 + (digest[1] / 255 - 0.5) * 0.06
        return Coordinates(f'{latitude:.6f}', f'{longitude:.6f}', approximate=True)
