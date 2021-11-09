# Copyright (c) 2020 Cisco and/or its affiliates.

# This software is licensed to you under the terms of the Cisco Sample
# Code License, Version 1.1 (the "License"). You may obtain a copy of the
# License at

#                https://developer.cisco.com/docs/licenses

# All use of the material herein must be in accordance with the terms of
# the License. All rights not expressly granted by the License are
# reserved. Unless required by applicable law or agreed to separately in
# writing, software distributed under the License is distributed on an "AS
# IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.

__author__ = "Chris McHenry"
__copyright__ = "Copyright (c) 2020 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.1"

from tetpyclient import MultiPartOption, RestClient
import boto3
import os
import json
import csv
from tempfile import NamedTemporaryFile

attributes = os.getenv('ATTRIBUTES_LIST')
add_tags = os.getenv('ADD_TAGS')
tetration_url = os.getenv('SECURE_WORKLOAD_URL')
tetration_api_key = os.getenv('SECURE_WORKLOAD_API_KEY')
tetration_api_secret = os.getenv('SECURE_WORKLOAD_API_SECRET')
tetration_tenant = os.getenv('SECURE_WORKLOAD_TENANT')
aws_region = os.getenv('WORKSPACE_REGION')
fields = {'IP', 'Cloud Service', 'Cloud', 'Location'}


def lambda_handler(event, context):
    workspaces = []
    ws_client = boto3.client('workspaces', region_name=aws_region)
    result = ws_client.describe_workspaces()
    for item in result['Workspaces']:
        tmp_item = {'IP': item['IpAddress'], 'Location': aws_region,
                    'Cloud Service': 'WorkSpaces', 'Cloud': 'AWS'}
        for attribute in attributes.split(','):
            fields.add(attribute)
            tmp_item[attribute] = item[attribute.strip()]
        if item['State'] in ['AVAILABLE', 'STOPPED']:
            if add_tags.lower() == 'true':
                get_tags(ws_client, tmp_item, item['WorkspaceId'])
            workspaces.append(tmp_item.copy())

    if len(workspaces) > 0:
        upload_tags(workspaces, 'overwrite')


def get_tags(ws_client, workspace, resource_id):
    tags = ws_client.describe_tags(ResourceId=resource_id)['TagList']
    for item in tags:
        fields.add(item['Key'])
        workspace[item['Key']] = item['Value']


def upload_tags(workspaces, action):
    restclient = RestClient(
        tetration_url,
        api_key=tetration_api_key,
        api_secret=tetration_api_secret,
        verify=False)

    with NamedTemporaryFile() as tf:
        with open(tf.name, 'w') as temp_csv:
            writer = csv.DictWriter(temp_csv, fieldnames=fields)
            writer.writeheader()
            for data in workspaces:
                writer.writerow(data)
            temp_csv.seek(0)
            req_payload = [
                MultiPartOption(
                    key='X-Tetration-Oper', val=action)
            ]
            resp = restclient.upload(
                temp_csv.name, '/openapi/v1/assets/cmdb/upload/{}'.format(
                    tetration_tenant), req_payload)
            if resp.ok:
                print("Uploaded {} Annotations \n Action: {}".format(
                    len(workspaces), action))
            else:
                print("Failed to Upload Annotations")
                print(resp.text)

#Testing
#lambda_handler(None, None)
