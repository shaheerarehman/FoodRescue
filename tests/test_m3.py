from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
import requests
from boto3.dynamodb.conditions import ConditionExpressionBuilder
from botocore.exceptions import ClientError

import geocoding_providers
import wiring
from geocoding import Coordinates, GeocodingUnavailable
from models import DonationCreate
from repository import DonationRepository, WriteConflict
from services import DonationService


NOW = datetime(2026, 11, 18, 15, tzinfo=timezone.utc)
FUTURE = (NOW + timedelta(hours=3)).isoformat()
ADDRESS = '123 King Street West, Hamilton'


@pytest.fixture
def service():
    repo = Mock(spec=DonationRepository)
    provider = Mock()
    return DonationService(repo, provider, now=lambda: NOW)


@pytest.mark.parametrize('name, provider_type', [
    ('google', geocoding_providers.GoogleGeocodingProvider),
    ('simulated', geocoding_providers.SimulatedGeocodingProvider),
])
def test_configuration_selects_provider(monkeypatch, name, provider_type):
    monkeypatch.setattr(wiring, 'GEOCODING_PROVIDER', name)
    assert isinstance(wiring.configured_provider(), provider_type)


def test_invalid_provider_is_rejected(monkeypatch):
    monkeypatch.setattr(wiring, 'GEOCODING_PROVIDER', 'unknown')
    with pytest.raises(ValueError, match='GEOCODING_PROVIDER'):
        wiring.configured_provider()


def test_simulated_provider_is_deterministic_and_offline(monkeypatch):
    request = Mock(side_effect=AssertionError('Network access'))
    monkeypatch.setattr(requests, 'get', request)
    provider = geocoding_providers.SimulatedGeocodingProvider()
    coordinates = provider.geocode(ADDRESS)
    assert coordinates == provider.geocode(ADDRESS.lower())
    assert coordinates.approximate
    assert 43.2 < float(coordinates.latitude) < 43.3
    request.assert_not_called()


@pytest.mark.parametrize('payload', [
    {'status': 'OVER_QUERY_LIMIT'},
    {'status': 'REQUEST_DENIED'},
    {'status': 'OK', 'results': []},
    None,
])
def test_google_errors_are_retryable(monkeypatch, payload):
    response = Mock()
    response.json.return_value = payload
    monkeypatch.setattr(requests, 'get', Mock(return_value=response))
    with pytest.raises(GeocodingUnavailable):
        geocoding_providers.GoogleGeocodingProvider('test').geocode(ADDRESS)


def test_google_timeout_is_retryable(monkeypatch):
    monkeypatch.setattr(requests, 'get', Mock(side_effect=requests.Timeout()))
    with pytest.raises(GeocodingUnavailable):
        geocoding_providers.GoogleGeocodingProvider('test').geocode(ADDRESS)


@pytest.mark.parametrize('payload, expected', [
    ({'status': 'ZERO_RESULTS'}, None),
    ({'status': 'OK', 'results': [{'geometry': {'location': {'lat': 43.25, 'lng': -79.87}}}]},
     Coordinates('43.25', '-79.87')),
])
def test_google_results(monkeypatch, payload, expected):
    response = Mock()
    response.json.return_value = payload
    monkeypatch.setattr(requests, 'get', Mock(return_value=response))
    assert geocoding_providers.GoogleGeocodingProvider('test').geocode(ADDRESS) == expected


def test_outage_donation_can_be_reserved_and_retried(service):
    service.geo.geocode.side_effect = GeocodingUnavailable
    service.repo.create.side_effect = lambda item: item
    donation = service.create_donation(DonationCreate(
        food_type='Bread', quantity='10', pickup_address=ADDRESS, pickup_deadline=FUTURE,
    ))
    assert donation['status'] == 'AVAILABLE'
    assert donation['geocoding_status'] == 'PENDING'
    assert 'latitude' not in donation
    service.repo.get.return_value = donation
    service.reserve_donation(donation['donation_id'], 'Charity')
    service.repo.reserve_atomically.assert_called_once_with(
        donation, 'Charity', NOW, NOW + timedelta(hours=2),
    )

    pending = {**donation, 'status': 'RESERVED', 'geocoding_retry_at': NOW.isoformat()}
    service.repo.scan_items.return_value = [pending]
    service.geo.geocode.side_effect = None
    service.geo.geocode.return_value = Coordinates('43.25', '-79.87')
    service.retry_geocoding()
    retry_at = (NOW + timedelta(minutes=5)).isoformat()
    service.repo.claim_geocoding_retry.assert_called_once_with(pending, retry_at)
    service.repo.finish_geocoding_retry.assert_called_once_with(pending, retry_at, {
        'geocoding_status': 'RESOLVED', 'latitude': '43.25', 'longitude': '-79.87',
        'coordinates_approximate': False,
    })


def test_retry_backoff_and_competing_worker(service):
    pending = {
        'status': 'AVAILABLE', 'geocoding_status': 'PENDING',
        'pickup_address': ADDRESS, 'pickup_deadline': FUTURE,
        'geocoding_retry_at': NOW.isoformat(),
    }
    deferred = {**pending, 'geocoding_retry_at': FUTURE}
    service.repo.scan_items.return_value = [pending, deferred]
    service.repo.claim_geocoding_retry.side_effect = WriteConflict
    service.retry_geocoding()
    service.repo.claim_geocoding_retry.assert_called_once()
    service.geo.geocode.assert_not_called()


@pytest.mark.parametrize('deadline, remaining_minutes, expected', [
    (FUTURE, 0, 'AVAILABLE'),
    (FUTURE, 1, None),
    (NOW.isoformat(), 1, 'EXPIRED'),
    ('invalid legacy deadline', 0, 'EXPIRED'),
])
def test_reservation_expiry(service, deadline, remaining_minutes, expected):
    item = {
        'donation_id': 'test', 'status': 'RESERVED', 'reserved_by': 'Charity',
        'pickup_deadline': deadline,
        'reservation_expires_at': (NOW + timedelta(minutes=remaining_minutes)).isoformat(),
    }
    service.repo.scan_items.return_value = [item]
    service.expire_due_donations()
    if expected:
        service.repo.update_status.assert_called_once_with(item, expected, release=True)
    else:
        service.repo.update_status.assert_not_called()


def test_legacy_reservation_gets_a_grace_period(service):
    item = {'status': 'RESERVED', 'pickup_deadline': FUTURE}
    service.repo.scan_items.return_value = [item]
    service.expire_due_donations()
    service.repo.start_legacy_reservation_timer.assert_called_once_with(
        item, NOW, NOW + timedelta(hours=2),
    )


def test_late_completion_is_rejected_before_worker_runs(service):
    service.repo.get.return_value = {
        'status': 'RESERVED', 'pickup_deadline': FUTURE,
        'reservation_expires_at': NOW.isoformat(),
    }
    with pytest.raises(ValueError, match='Pickup window'):
        service.complete_donation('test')
    service.repo.update_status.assert_not_called()


def test_scan_reads_past_empty_page():
    repo = DonationRepository.__new__(DonationRepository)
    repo.table = Mock()
    key = {'donation_id': 'page-1'}
    repo.table.scan.side_effect = [
        {'Items': [], 'LastEvaluatedKey': key}, {'Items': [{'donation_id': 'page-2'}]},
    ]
    assert repo.list_all() == [{'donation_id': 'page-2'}]
    repo.table.scan.assert_called_with(ExclusiveStartKey=key)


def test_expiry_checks_reservation_identity_and_clears_claim():
    repo = DonationRepository.__new__(DonationRepository)
    repo.table = Mock()
    repo.table.update_item.side_effect = ClientError(
        {'Error': {'Code': 'ConditionalCheckFailedException'}}, 'UpdateItem',
    )
    with pytest.raises(WriteConflict):
        repo.update_status({
            'donation_id': 'test', 'status': 'RESERVED', 'reservation_id': 'old-reservation',
        }, 'AVAILABLE', release=True)
    request = repo.table.update_item.call_args.kwargs
    condition = ConditionExpressionBuilder().build_expression(request['ConditionExpression'])
    assert condition.condition_expression == '(#n0 = :v0 AND #n1 = :v1)'
    assert condition.attribute_name_placeholders == {'#n0': 'status', '#n1': 'reservation_id'}
    assert condition.attribute_value_placeholders == {':v0': 'RESERVED', ':v1': 'old-reservation'}
    assert request['ExpressionAttributeValues'][':value1'] == ''
    assert {name for token, name in request['ExpressionAttributeNames'].items()
            if token.startswith('#remove')} == {
        'reservation_id', 'reserved_at', 'reservation_expires_at',
    }
