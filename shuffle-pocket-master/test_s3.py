from __future__ import print_function
import numpy as np


import boto3

client = boto3.client('s3', 'us-west-2')

randomized_keyname = "input/76514d3c-part-0"
obj = client.get_object(Bucket="yupeng-pywren", Key = randomized_keyname)
fileobj = obj['Body']
recordType = np.dtype([('key', 'S4'), ('value', 'S96')])
data = np.frombuffer(fileobj.read(), dtype=recordType)
print(data)

