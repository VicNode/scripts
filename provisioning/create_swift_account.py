#!/usr/bin/env python

# VicNode swift provisioning script
#
# Creates a swift account and sets quota for a user.
# You must have the ResellerAdmin role to be able to run this
#

import os
import argparse

from swiftclient import client


def create_swift_account(sc, tenant_id, quota_bytes):
    url, token = sc.get_auth()
    base_url = url.split('_')[0] + '_'
    tenant_url = base_url + tenant_id

    client.post_account(url=tenant_url,
                        token=token,
                        headers={'X-Account-Meta-Quota-Bytes': quota_bytes})


def get_swift_client():

    auth_username = os.environ.get('OS_USERNAME')
    auth_password = os.environ.get('OS_PASSWORD')
    auth_tenant = os.environ.get('OS_TENANT_NAME')
    auth_url = os.environ.get('OS_AUTH_URL')

    sc = client.Connection(authurl=auth_url,
                           user=auth_username,
                           key=auth_password,
                           tenant_name=auth_tenant,
                           auth_version=2,
                           os_options={'region_name': 'VicNode'})

    return sc


def collect_args():

    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    parser.add_argument('-p', '--project_id', action='store',
                        required=True, help='Project ID')
    parser.add_argument('-b', '--bytes', action='store',
                        required=True, type=int,
                        help='Total bytes of object quota')

    return parser


if __name__ == '__main__':

    args = collect_args().parse_args()

    project_id = args.project_id
    quota_bytes = args.bytes

    sc = get_swift_client()
    create_swift_account(sc, project_id, quota_bytes)
