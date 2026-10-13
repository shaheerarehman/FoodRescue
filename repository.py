import boto3
from botocore.exceptions import ClientError

from config import AWS_REGION, TABLE_NAME


class DonationRepository:
    """Contains DynamoDB access so persistence changes stay out of route/business code."""

    def __init__(self):
        self.table = boto3.resource('dynamodb', region_name=AWS_REGION).Table(TABLE_NAME)

    def create(self, item):
        self.table.put_item(Item=item, ConditionExpression='attribute_not_exists(donation_id)')
        return item

    def get(self, donation_id):
        return self.table.get_item(Key={'donation_id': donation_id}).get('Item')

    def list_all(self):
        return self.table.scan().get('Items', [])

    def list_available(self):
        return [x for x in self.list_all() if x.get('status') == 'AVAILABLE']

    def reserve_atomically(self, donation_id, charity_name):
        try:
            return self.table.update_item(
                Key={'donation_id': donation_id},
                UpdateExpression='SET #s=:reserved, reserved_by=:charity',
                ConditionExpression='#s=:available',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':reserved': 'RESERVED',
                    ':available': 'AVAILABLE',
                    ':charity': charity_name,
                },
                ReturnValues='ALL_NEW',
            )['Attributes']
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ValueError('Donation is no longer available')
            raise

    def update_status(self, donation_id, old_status, new_status):
        try:
            return self.table.update_item(
                Key={'donation_id': donation_id},
                UpdateExpression='SET #s=:new',
                ConditionExpression='#s=:old',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':new': new_status, ':old': old_status},
                ReturnValues='ALL_NEW',
            )['Attributes']
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ValueError('Donation status changed; refresh and try again')
            raise
