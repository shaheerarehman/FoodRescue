import os, boto3
region=os.getenv('AWS_REGION','ca-central-1'); name=os.getenv('DYNAMODB_TABLE','FoodRescueDonations')
ddb=boto3.client('dynamodb',region_name=region)
try:
    ddb.create_table(TableName=name, KeySchema=[{'AttributeName':'donation_id','KeyType':'HASH'}], AttributeDefinitions=[{'AttributeName':'donation_id','AttributeType':'S'}], BillingMode='PAY_PER_REQUEST')
    ddb.get_waiter('table_exists').wait(TableName=name)
    print('Created',name)
except ddb.exceptions.ResourceInUseException:
    print(name,'already exists')
