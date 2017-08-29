#!/usr/bin/env python

# VicNode swift provisioning script
#
# Creates a swift account and sets quota for a user.
# You must have the ResellerAdmin role to be able to run this
#

import os
import sys
import argparse

from swiftclient import client as swiftclient
from swiftclient.exceptions import ClientException as sc_exception

SWIFT_QUOTA_KEY = 'X-Account-Meta-Quota-Bytes'.lower()


def set_swift_quota(sc, tenant_id, quota):
    tenant_url, token = get_swift_tenant_connection(sc, tenant_id)
    try:
        print 'Setting quota for project %s to %s bytes' % \
            (tenant_id, quota)
        swiftclient.post_account(url=tenant_url,
                                 token=token,
                                 headers={SWIFT_QUOTA_KEY: quota})
    except:
        print 'Failed to set quota for project %s to %s bytes' % \
            (tenant_id, quota)


def get_swift_tenant_connection(sc, tenant_id):
    try:
        url, token = sc.get_auth()
    except:
        print 'Have you sourced your openrc?'
        sys.exit(1)
    base_url = url.split('_')[0] + '_'
    return base_url + tenant_id, token


def get_swift_quota(sc, tenant_id):
    tenant_url, token = get_swift_tenant_connection(sc, tenant_id)
    try:
        swift_account = swiftclient.head_account(url=tenant_url, token=token)
    except sc_exception:
        print 'Project %s has no swift quota' % tenant_id
        return
    return swift_account.get(SWIFT_QUOTA_KEY, -1)

def get_swift_client():
    auth_username = os.environ.get('OS_USERNAME')
    auth_password = os.environ.get('OS_PASSWORD')
    auth_url = os.environ.get('OS_AUTH_URL')+"/v3"
    auth_options = {
        'region_name': 'VicNode',
        'project_name': os.environ.get('OS_TENANT_NAME')
    }

    sc = swiftclient.Connection(authurl=auth_url,
                                user=auth_username,
                                key=auth_password,
                                auth_version='3',
                                os_options=auth_options)

    return sc

def pretty_gb(b):
    return str(round(b_to_gb(b), 3))


def b_to_gb(b):
    return (float(b) / 1000.0 / 1000.0 / 1000.0)


def pretty_tb(b):
    return str(round(b_to_tb(b), 3))


def b_to_tb(b):
    return (float(b) / 1000.0 / 1000.0 / 1000.0 / 1000.0)


def tb_to_b(tb):
    try:
        b = int(tb) * 1000 * 1000 * 1000 * 1000
    except ValueError as e:
        print e
        print 'Error: Invalid TB value specified: %s' % tb
        sys.exit(1)
    return b


def gb_to_b(gb):
    try:
        b = int(gb) * 1000 * 1000 * 1000
    except ValueError as e:
        print e
        print 'Error: Invalid GB value specified: %s' % gb
        sys.exit(1)
    return b


def get_bytes(value):
    if value.endswith('TB') or value.endswith('T'):
        return tb_to_b(value.rstrip('TB'))
    if value.endswith('GB') or value.endswith('G'):
        return gb_to_b(value.rstrip('GB'))
    return int(value)


def collect_args():

    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    parser.add_argument('-p', '--project_id', action='store',
                        required=True, help='Project ID')
    parser.add_argument('-b', '--bytes', action='store',
                        required=False, default='-1', type=get_bytes,
                        help='Total bytes of object quota')

    return parser


if __name__ == '__main__':

    args = collect_args().parse_args()

    project_id = args.project_id
    quota_bytes = args.bytes

    sc = get_swift_client()

    quota = get_swift_quota(sc, project_id)
    if quota is not None:
        print 'Current quota for project %s:   %s bytes (%s GB)' % \
            (project_id, quota, pretty_gb(quota))

    if quota_bytes >= 0:
        set_swift_quota(sc, project_id, quota_bytes)

        quota = get_swift_quota(sc, project_id)
        print 'New quota for project %s:       %s bytes (%s GB)' % \
            (project_id, quota, pretty_gb(quota))
