#!/usr/bin/python
import argparse
import sys

from os import environ
from re import sub as substitute

from keystoneclient.v2_0 import client as keystonec
from swiftclient import client as swiftc
from cinderclient import client as cinderc

def main():

    parser = argparse.ArgumentParser(description='VicNode reporting tool')
    subparsers = parser.add_subparsers()

    parser_allocation = subparsers.add_parser('allocation', help='Report on current allocations')
    parser_allocation.add_argument('-i', '--insecure', action='store_true', help='Whether to connect to endpoints using insecure SSL')
    parser_allocation.add_argument('-u', '--username', help='Openstack username to use when connecting')
    parser_allocation.add_argument('-p', '--password', help='Openstack password to use when connecting')
    parser_allocation.add_argument('-t', '--tenant', help='Openstack tenant to use when connecting')
    parser_allocation.add_argument('-a', '--auth_url', help='Openstack endpoint url to authenticate against')
    parser_allocation.add_argument('-s', '--swift_region', help='Name of the Swift region to reoprt on')
    parser_allocation.set_defaults(func=report_allocation)

    parser_capacity  = subparsers.add_parser('capacity', help='Report on current capacity')
    parser_capacity.add_argument('-f', '--filer', help='Address or hostname of NetApp filer')
    parser_capacity.add_argument('-u', '--username', help='Username to use when connecting to NetApp filer')
    parser_capacity.add_argument('-p', '--password', help='Password to use when connecting to NetApp filer')
    parser_capacity.set_defaults(func=report_capacity)

    args = parser.parse_args()
    args.func(args)

def report_allocation(args):
    creds = {}
    creds['insecure'] = args.insecure

    if args.username == None:
        if 'OS_USERNAME' not in environ:
            print 'OpenStack username environment variable OS_USERNAME not set and -u not used'
            sys.exit(1)
        else:
            creds['username'] = environ['OS_USERNAME']
    else:
        creds['username'] = args.username

    if args.password== None:
        if 'OS_PASSWORD' not in environ:
            print 'OpenStack password environment variable OS_PASSWORD not set and -p not used'
            sys.exit(1)
        else:
            creds['password'] = environ['OS_PASSWORD']
    else:
        creds['password'] = args.password

    if args.tenant == None:
        if 'OS_TENANT_NAME' not in environ:
            print 'OpenStack tenant name environment variable OS_TENANT_NAME not set and -t not used'
            sys.exit(1)
        else:
            creds['tenant_name'] = environ['OS_TENANT_NAME']
    else:
        creds['tenant_name'] = args.tenant

    if args.auth_url == None:
        if 'OS_AUTH_URL' not in environ:
            print 'OpenStack auth url environment variable OS_AUTH_URL not set and -a not used'
            sys.exit(1)
        else:
            creds['auth_url'] = environ['OS_AUTH_URL']
    else:
        creds['auth_url'] = args.auth_url

    if args.swift_region == None:
        if 'OS_SWIFT_REGION_NAME' not in environ:
            print 'OpenStack swift region name environment variable OS_SWIFT_REGION_NAME not set and -s not used'
            sys.exit(1)
        else:
            creds['region_name'] = environ['OS_SWIFT_REGION_NAME']
    else:
        creds['region_name'] = args.swift_region

    merit_allocations = list_merit_allocations(creds)
  
    swift = swiftc.Connection(authurl=creds['auth_url'],
                              user=creds['username'],
                              key=creds['password'],
                              tenant_name=creds['tenant_name'],
                              insecure=creds['insecure'],
                              os_options={'region_name': creds['region_name']},
                              auth_version='2.0')
  
    swift.head_account()
    swift_auth_url = substitute('AUTH_.*','AUTH_', swift.url)
  
    print "tenant_id, vicnode_id, swift_quota, swift_used, cinder_quota, cinder_used, total_allocation_quota, total_allocation_used"
  
    for tenant in merit_allocations:
  
        creds['region_name'] = environ['OS_SWIFT_REGION_NAME']
        swift_usage_info = allocation_swift_usage(creds, tenant.id, swift_auth_url)
  
        creds['region_name'] = environ['OS_CINDER_REGION_NAME']
        cinder_usage_info = allocation_cinder_usage(creds, tenant.id)
      
        print ', '.join([tenant.id,
                         tenant.vicnode_id,
                         str(swift_usage_info['gb_allocated']),
                         str(round(swift_usage_info['gb_used'], 2) ),
                         str(cinder_usage_info['gb_allocated']),
                         str(cinder_usage_info['gb_used']),
                         str(swift_usage_info['gb_allocated'] + cinder_usage_info['gb_allocated']),
                         str(swift_usage_info['gb_used'] + cinder_usage_info['gb_used'])])

def list_merit_allocations(creds):

    merit_allocation_tenants = []

    try:
        client = keystonec.Client(username=creds['username'],
                                  password=creds['password'],
                                  tenant_name=creds['tenant_name'],
                                  insecure=creds['insecure'],
                                  auth_url=creds['auth_url'],
                                  region_name=creds['region_name'])
    except:
        print('Failed to connect to Keystone')
        sys.exit(1)

    return [ tenant for tenant in client.tenants.list() if hasattr(tenant, 'vicnode_id') ]

def allocation_cinder_usage(creds, tenant_id):

    usage = {}

    try:
        cinder = cinderc.Client('1',
                              creds['username'],
                              creds['password'],
                              project_id=creds['tenant_name'],
                              auth_url=creds['auth_url'],
                              insecure=creds['insecure'],
                              region_name=creds['region_name'])
    except:
        print('Failed to connect to Cinder')
        sys.exit(1)


    quota_info = float(cinder.quotas.get(tenant_id).gigabytes)
    if quota_info > 0:
        usage['gb_allocated'] = float(cinder.quotas.get(tenant_id).gigabytes)
    else:
        usage['gb_allocated'] = float(0)

    usage['gb_used'] = usage['gb_allocated']

    return usage

def allocation_swift_usage(creds, tenant_id, swift_auth_url):

    usage = {}

    try:
        swift = swiftc.Connection(authurl=creds['auth_url'],
                                user=creds['username'],
                                key=creds['password'],
                                tenant_name=creds['tenant_name'],
                                insecure=creds['insecure'],
                                os_options={'region_name': creds['region_name'],
                                            'object_storage_url': swift_auth_url + tenant_id},
                                auth_version='2.0')
    except:
        print('Failed to connect to Swift')
        sys.exit(1)

    account_info = swift.head_account()

    if 'x-account-meta-account-bytes' in account_info:
        usage['gb_allocated'] = float(account_info['x-account-meta-account-bytes'])/1024/1024/1024
    else:
        usage['gb_allocated'] = float(0)

    usage['gb_used'] = float(account_info['x-account-bytes-used'])/1024/1024/1024

    return usage

def report_capacity(args):
    pass

if __name__ == '__main__':
    main()
