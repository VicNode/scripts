#!/usr/bin/env python

# VicNode id creation script
#
# Adds a VicNode ID to a tenant
#


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


def update_vicnode_id(tenant, vicnode_id):
    """Used in RDSI reporting to determine if the allocation should appear
    in the report.

    """
    if vicnode_id is not None:
        print 'Updating tenant %s with VicNode ID %s' % (tenant.id, vicnode_id)
        kc.tenants.update(tenant.id, vicnode_id=vicnode_id)


def get_vicnode_id(tenant):
    if hasattr(tenant, 'vicnode_id'):
        return tenant.vicnode_id


def collect_args():

    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    parser.add_argument('-p', '--project_id', action='store',
                        required=True, help='The project ID')
    parser.add_argument('-v', '--vicnode_id', action='store', default=None,
                        required=False, help='The new VicNode id of the tenant')
    return parser


if __name__ == '__main__':

    args = vars(collect_args().parse_args())
    project_id = args['project_id']
    vicnode_id = args['vicnode_id']

    kc = get_keystone_client()

    tenant = get_tenant(kc, project_id)
    current_vicnode_id = get_vicnode_id(tenant)
    print 'Existing VicNode ID: %s' % current_vicnode_id

    if vicnode_id is not None:
        update_vicnode_id(tenant, vicnode_id)
