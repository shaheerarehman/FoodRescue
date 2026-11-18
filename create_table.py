import boto3

from config import AWS_REGION, TABLE_NAME

name = TABLE_NAME
ddb = boto3.client('dynamodb', region_name=AWS_REGION)
try:
    ddb.create_table(TableName=name, KeySchema=[{'AttributeName':'donation_id','KeyType':'HASH'}], AttributeDefinitions=[{'AttributeName':'donation_id','AttributeType':'S'}], BillingMode='PAY_PER_REQUEST')
    ddb.get_waiter('table_exists').wait(TableName=name)
    print('Created',name)
except ddb.exceptions.ResourceInUseException:
    print(name,'already exists')
