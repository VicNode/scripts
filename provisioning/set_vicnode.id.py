#!/usr/bin/env python

import os
import sys
import argparse

from keystoneclient.v2_0 import client as ks_client
from keystoneclient.exceptions import AuthorizationFailure, NotFound


def get_keystone_client():

    auth_username = os.environ.get('OS_USERNAME')
    auth_password = os.environ.get('OS_PASSWORD')
    auth_tenant = os.environ.get('OS_TENANT_NAME')
    auth_url = os.environ.get('OS_AUTH_URL')

    try:
        kc = ks_client.Client(username=auth_username,
                              password=auth_password,
                              tenant_name=auth_tenant,
                              auth_url=auth_url)
    except AuthorizationFailure as e:
        print e
        print 'Authorization failed, have you sourced your openrc?'
        sys.exit(1)

    return kc


def get_tenant(keystone, name_or_id):
    try:
        tenant = keystone.tenants.get(name_or_id)
    except NotFound:
        tenant = keystone.tenants.find(name=name_or_id)
    return tenant


def update_vicnode_id(kc, tenant_id, vicnode_id):
    """Used in RDSI reporting to determine if the allocation should appear
    in the report.

    """
    tenant = get_tenant(kc, tenant_id)
    kc.tenants.update(tenant.id, vicnode_id=vicnode_id)


def collect_args():

    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    parser.add_argument('-t', '--tenant_id', action='store',
                        required=True, help='The tenant ID')
    parser.add_argument('-v', '--vicnode_id', action='store',
                        required=True, help='The new VicNode id of the tenant')
    return parser


if __name__ == '__main__':

    args = vars(collect_args().parse_args())
    tenant_id = args['tenant_id']
    vicnode_id = args['vicnode_id']

    kc = get_keystone_client()

    tenant = update_vicnode_id(kc, tenant_id, vicnode_id)
