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
delete_sensors = os.getenv('DELETE_SENSORS')
tetration_url = os.getenv('SECURE_WORKLOAD_URL')
tetration_api_key = os.getenv('SECURE_WORKLOAD_API_KEY')
tetration_api_secret = os.getenv('SECURE_WORKLOAD_API_SECRET')
tetration_tenant = os.getenv('SECURE_WORKLOAD_TENANT')
aws_region = os.getenv('WORKSPACE_REGION')


def lambda_handler(event, context):

    workspaces_tagged = get_tetration_tagged_workspaces()
    workspaces_active = get_aws_workspaces()

    workspaces_to_delete = [
        x for x in workspaces_tagged if x['ip'] not in workspaces_active]

    if len(workspaces_to_delete) > 0:
        print('INFO: The following workspaces references will be cleaned up in Tetration {}'.format(
            json.dumps(workspaces_to_delete)))
        delete_tags(workspaces_to_delete, 'delete')
        if delete_sensors.lower() == 'true':
            delete_terminated_agents(workspaces_to_delete)
    else:
        print('INFO: No Workspaces have been terminated')


def get_tetration_tagged_workspaces():
    restclient = RestClient(
        tetration_url,
        api_key=tetration_api_key,
        api_secret=tetration_api_secret,
        verify=False)

    req_payload = {
        "filter": {"type": "and", "filters": [
            {"type": "eq", "field": "user_Location", "value": aws_region},
            {"type": "eq", "field": "user_Cloud Service", "value": "WorkSpaces"}
        ]},
        "scopeName": tetration_tenant,
        "dimensions": ['ip', 'host_uuid', "user_Cloud Service", "user_Location"],
        "limit": 2000
    }

    resp = restclient.post('/inventory/search',
                           json_body=json.dumps(req_payload))

    if resp.status_code == 200:
        parsed_resp = json.loads(resp.content)
        return parsed_resp['results']


def get_aws_workspaces():
    workspaces = set()
    ws_client = boto3.client('workspaces', region_name=aws_region)
    result = ws_client.describe_workspaces()
    for item in result['Workspaces']:
        workspaces.add(item['IpAddress'])
    return workspaces


def delete_tags(workspaces, action):
    print('Deleting tags...')
    to_delete = []
    for item in workspaces:
        to_delete.append(
            {'ip': item['ip'], 'Cloud Service': item['user_Cloud Service']})

    restclient = RestClient(
        tetration_url,
        api_key=tetration_api_key,
        api_secret=tetration_api_secret,
        verify=False)

    with NamedTemporaryFile() as tf:
        with open(tf.name, 'w') as temp_csv:
            writer = csv.DictWriter(temp_csv, fieldnames=[
                                    'ip', 'Cloud Service'])
            writer.writeheader()
            for data in to_delete:
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
                print("INFO: Deleted {} Annotations".format(
                    len(workspaces)))
            else:
                print("ERROR: Failed to Upload Annotations")
                print(resp.text)


def delete_terminated_agents(agents_to_delete):
    restclient = RestClient(
        tetration_url,
        api_key=tetration_api_key,
        api_secret=tetration_api_secret,
        verify=False)

    for agent in agents_to_delete:
        print('INFO: Deleting sensor with uuid: {}'.format(agent['host_uuid']))
        resp = restclient.delete(
            '/openapi/v1/sensors/{}'.format(agent['host_uuid']))
        if resp.ok:
            print('INFO: Deleted sensor with uuid: {}'.format(
                agent['host_uuid']))
        else:
            print("ERROR: Failed to Deleted sensor with uuid: {}".format(
                agent['host_uuid']))
            print(resp.text)


lambda_handler(None, None)
# print(json.dumps(get_tetration_tagged_workspaces(),indent=1))
# print(get_aws_workspaces())
