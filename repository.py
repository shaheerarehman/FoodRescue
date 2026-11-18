import uuid

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from config import AWS_REGION, TABLE_NAME


class WriteConflict(ValueError):
    """A conditional write lost a race with another process."""


class DonationRepository:
    """Contains DynamoDB access so persistence stays out of business logic."""

    def __init__(self):
        self.table = boto3.resource('dynamodb', region_name=AWS_REGION).Table(TABLE_NAME)

    def create(self, item):
        self.table.put_item(Item=item, ConditionExpression='attribute_not_exists(donation_id)')
        return item

    def get(self, donation_id):
        return self.table.get_item(
            Key={'donation_id': donation_id}, ConsistentRead=True,
        ).get('Item')

    def scan_items(self):
        page = self.table.scan()
        yield from page.get('Items', [])
        while page.get('LastEvaluatedKey'):
            page = self.table.scan(ExclusiveStartKey=page['LastEvaluatedKey'])
            yield from page.get('Items', [])

    def list_all(self):
        return list(self.scan_items())

    def list_available(self):
        return [item for item in self.scan_items() if item.get('status') == 'AVAILABLE']

    def _update(self, item, condition, changes, remove=()):
        names = {f'#field{i}': name for i, name in enumerate(changes)}
        values = {f':value{i}': value for i, value in enumerate(changes.values())}
        assignments = [f'{name}={value}' for name, value in zip(names, values)]
        expression = 'SET ' + ', '.join(assignments)
        if remove:
            removals = {f'#remove{i}': name for i, name in enumerate(remove)}
            names.update(removals)
            expression += ' REMOVE ' + ', '.join(removals)
        try:
            return self.table.update_item(
                Key={'donation_id': item['donation_id']},
                UpdateExpression=expression,
                ConditionExpression=condition,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ReturnValues='ALL_NEW',
            )['Attributes']
        except ClientError as error:
            if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise WriteConflict('Donation changed; refresh and try again') from None
            raise

    @staticmethod
    def _matches(item, field):
        attr = Attr(field)
        return attr.eq(item[field]) if field in item else attr.not_exists()

    def _same_reservation(self, item):
        return Attr('status').eq(item['status']) & self._matches(item, 'reservation_id')

    def reserve_atomically(self, item, charity_name, now, expires):
        condition = Attr('status').eq('AVAILABLE') & self._matches(item, 'pickup_deadline')
        return self._update(item, condition, {
            'status': 'RESERVED',
            'reserved_by': charity_name,
            'reservation_id': str(uuid.uuid4()),
            'reserved_at': now.isoformat(),
            'reservation_expires_at': expires.isoformat(),
        })

    def update_status(self, item, new_status, *, release=False):
        condition = self._same_reservation(item)
        if release:
            return self._update(
                item, condition, {'status': new_status, 'reserved_by': ''},
                remove=('reservation_id', 'reserved_at', 'reservation_expires_at'),
            )
        return self._update(item, condition, {'status': new_status})

    def start_legacy_reservation_timer(self, item, now, expires):
        condition = self._same_reservation(item) & self._matches(item, 'reservation_expires_at')
        return self._update(item, condition, {
            'reservation_id': str(uuid.uuid4()),
            'reserved_at': now.isoformat(),
            'reservation_expires_at': expires.isoformat(),
        })

    @staticmethod
    def _pending_geocoding(item):
        return (
            Attr('status').is_in(['AVAILABLE', 'RESERVED'])
            & Attr('geocoding_status').eq('PENDING')
            & Attr('pickup_address').eq(item['pickup_address'])
        )

    def claim_geocoding_retry(self, item, retry_at):
        condition = self._pending_geocoding(item) & self._matches(item, 'geocoding_retry_at')
        return self._update(item, condition, {'geocoding_retry_at': retry_at})

    def finish_geocoding_retry(self, item, retry_at, result):
        condition = self._pending_geocoding(item) & Attr('geocoding_retry_at').eq(retry_at)
        return self._update(item, condition, result, remove=('geocoding_retry_at',))
