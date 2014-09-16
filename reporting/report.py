#!/usr/bin/python
# Copyright (C) 2014 Aptira <info@aptira.com>
#
# Author: Michael Chapman   <michael@aptira.com>
# Author: Sina Sadeghi      <sina@aptira.com>
#
import argparse
import sys
sys.path.append("./NetApp/lib/python/NetApp")
from NaServer import NaServer
from NaElement import NaElement

from os import environ
import re

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
    parser_allocation.add_argument('-s', '--swift_region', help='Name of the Swift region to report on')
    parser_allocation.add_argument('-c', '--cinder_region', help='Name of the Cinder region to report on')
    parser_allocation.set_defaults(func=report_allocation)

    parser_capacity  = subparsers.add_parser('capacity', help='Report on current capacity')
    parser_capacity.add_argument('-f', '--filer', required=True, help='Address or hostname of NetApp filer')
    parser_capacity.add_argument('-u', '--username', required=True, help='Username to use when connecting to NetApp filer')
    parser_capacity.add_argument('-p', '--password', required=True, help='Password to use when connecting to NetApp filer')
    parser_capacity.set_defaults(func=report_capacity)

    parser_market  = subparsers.add_parser('market', help='Report on Market ')
    parser_market.add_argument('-f', '--filer', required=True, help='Address or hostname of NetApp filer')
    parser_market.add_argument('-u', '--username', required=True, help='Username to use when connecting to NetApp filer')
    parser_market.add_argument('-p', '--password', required=True, help='Password to use when connecting to NetApp filer')
    parser_market.set_defaults(func=report_market)

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
            creds['swift_region_name'] = environ['OS_SWIFT_REGION_NAME']
    else:
        creds['swift_region_name'] = args.swift_region

    if args.cinder_region == None:
        if 'OS_CINDER_REGION_NAME' not in environ:
            print 'OpenStack cinder region name environment variable OS_CINDER_REGION_NAME not set and -c not used'
            sys.exit(1)
        else:
            creds['cinder_region_name'] = environ['OS_CINDER_REGION_NAME']
    else:
        creds['cinder_region_name'] = args.cinder_region

    merit_allocations = list_merit_allocations(creds)

    swift = swiftc.Connection(authurl=creds['auth_url'],
                              user=creds['username'],
                              key=creds['password'],
                              tenant_name=creds['tenant_name'],
                              insecure=creds['insecure'],
                              os_options={'region_name': creds['swift_region_name']},
                              auth_version='2.0')

    swift.head_account()
    swift_auth_url = re.sub('AUTH_.*','AUTH_', swift.url)

    print "tenant_id, vicnode_id, swift_quota, swift_used, cinder_quota, cinder_used, total_allocation_quota, total_allocation_used"

    for tenant in merit_allocations:

        #creds['region_name'] = environ['OS_SWIFT_REGION_NAME']
        swift_usage_info = allocation_swift_usage(creds, tenant.id, swift_auth_url)

        #creds['region_name'] = environ['OS_CINDER_REGION_NAME']
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
                                  region_name=creds['cinder_region_name'])
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
                              region_name=creds['cinder_region_name'])
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
                                os_options={'region_name': creds['swift_region_name'],
                                            'object_storage_url': swift_auth_url + tenant_id},
                                auth_version='2.0')
    except:
        print('Failed to connect to Swift')
        sys.exit(1)

    account_info = swift.head_account()

    if 'x-account-meta-account-bytes' in account_info:
        usage['gb_allocated'] = float(account_info['x-account-meta-account-bytes'])/1000/1000/1000
    else:
        usage['gb_allocated'] = float(0)

    usage['gb_used'] = float(account_info['x-account-bytes-used'])/1000/1000/1000

    return usage

def report_capacity(args):
    connection = initialise(args.filer, args.username, args.password)
    report_disks(connection)
    report_aggregates(connection)
    report_volumes(connection)

def report_disks(connection):
    disks = get_disks(connection)
    raw_stats = raw_storage_stats(disks)
    disk_types = get_disk_types(raw_stats)
    print_raw_stats(raw_stats, disk_types)

def report_volumes(connection):
    volumes = get_volumes(connection)
    volume_stats = get_volume_stats(volumes)

def report_aggregates(connection):
    aggrs = get_aggrs(connection)
    aggr_stats = get_aggr_stats(aggrs)
    print_aggrs(aggr_stats)

# The market has one vserver perAuser
def report_market(args):
    connection = initialise(args.filer, args.username, args.password)
    vservers = get_vservers(connection)
    volumes = get_volumes(connection)
    vserver_stats = get_vserver_stats(vservers, volumes)

# Initialise filer connection and return connection object
def initialise(filer, user, pw):
    s = NaServer(filer, 1, 3)
    response = s.set_style('LOGIN')
    if(response and response.results_errno() != 0 ):
        r = response.results_reason()
        print ("Unable to set authentication style " + r + "\n")
        sys.exit (2)

    s.set_admin_user(user, pw)
    response = s.set_transport_type('HTTP')

    if(response and response.results_errno() != 0 ):
        r = response.results_reason()
        print ("Unable to set HTTP transport " + r + "\n")
        sys.exit (2)

    return s

def get_aggrs(s):
    out = s.invoke("aggr-get-iter")

    if(out.results_status() == "failed"):
        print (out.results_reason() + "\n")
        sys.exit (2)

    return out.child_get('attributes-list').children_get()

def get_aggr_stats(aggrs):
    aggr_stats = {}
    for aggr in aggrs:
        name = aggr.child_get_string("aggregate-name")
        owner = aggr.child_get("aggr-ownership-attributes").child_get_string('owner-name')

        available = aggr.child_get("aggr-space-attributes").child_get_string('size-available')
        total = aggr.child_get("aggr-space-attributes").child_get_string('size-total')
        used = aggr.child_get("aggr-space-attributes").child_get_string('size-used')

        if owner not in aggr_stats:
            aggr_stats[owner] = [{'name' : name, 'available': available, 'total': total, 'used': used}]
        else:
            aggr_stats[owner].append({'name' : name, 'available': available, 'total': total, 'used': used})
    return aggr_stats

def print_aggrs(aggr_stats):
    print 'Aggregate Statistics:'
    print ', '.join(['owner', 'name', 'total', 'used', 'available'])
    for owner,li in aggr_stats.items():
        for data in li:
            print ', '.join([owner, data['name'], pretty_tb(data['total']),  pretty_tb(data['used']), pretty_tb(data['available'])])

# Get a list of non-admin vservers
def get_vservers(s):
    out = s.invoke("vserver-get-iter")

    if(out.results_status() == "failed"):
        print (out.results_reason() + "\n")
        sys.exit (2)

    attributes = out.child_get('attributes-list')
    servers = attributes.children_get()

    return [ server for server in servers if server.child_get_string('vserver-type') == 'data' ]

def get_vserver_stats(servers, volumes):
    print 'Market VServer Stats:'
    stats = {}
    serverids = { server.child_get_string('uuid'): server.child_get_string('vserver-name') for server in servers }
    for volume in volumes:
        vol_id_attrs = volume.child_get('volume-id-attributes')
        vol_space_attrs = volume.child_get('volume-space-attributes')
        vserver = vol_id_attrs.child_get_string('owning-vserver-name')

        if vserver.startswith('os_'):
            vserver_uuid = vol_id_attrs.child_get_string('owning-vserver-uuid')
            total = vol_space_attrs.child_get_int('size-total')
            used = vol_space_attrs.child_get_int('size-used')
            available = vol_space_attrs.child_get_int('size-available')
            if vserver_uuid in serverids:
                if vserver_uuid not in stats:
                    stats[vserver_uuid] = { 'volume_count': 1, 'total': total, 'used': used, 'available': available }
                else:
                    stats[vserver_uuid]['total'] += total
                    stats[vserver_uuid]['used'] += used
                    stats[vserver_uuid]['available'] += available
                    stats[vserver_uuid]['volume_count'] += 1

    print ', '.join(['vserver_name', 'total','used','available','volume_count'])
    for vserver_uuid, data in stats.items():
        print ', '.join([serverids[vserver_uuid], pretty_tb(data['total']), pretty_tb(data['used']), pretty_tb(data['available']), str(data['volume_count'])])

def get_volumes(s):
    cmd = NaElement('volume-get-iter')
    cmd.child_add_string('max-records', 500)
    out = s.invoke_elem(cmd)

    if(out.results_status() == "failed"):
        print (out.results_reason() + "\n")
        sys.exit (2)

    attributes = out.child_get('attributes-list')
    return attributes.children_get()

def get_volume_stats(volumes):
    print ''
    print 'Volume stats:'
    print ', '.join(['name', 'vserver', 'aggr', 'total', 'used', 'available'])
    for volume in volumes:
        vol_id_attrs = volume.child_get('volume-id-attributes')
        vol_space_attrs = volume.child_get('volume-space-attributes')
        vserver = vol_id_attrs.child_get_string('owning-vserver-name')
        name = vol_id_attrs.child_get_string('name')

        if vserver.startswith('os_') and name.find('rootvol') != 0:
              aggr = vol_id_attrs.child_get_string('containing-aggregate-name')
              total = vol_space_attrs.child_get_string('size-total')
              used = vol_space_attrs.child_get_string('size-used')
              available = vol_space_attrs.child_get_string('size-available')
              print ', '.join([name, vserver, aggr, pretty_tb(total), pretty_tb(used), pretty_tb(available)])


## Get a list of all disks in the cluster
def get_disks(s):
    out = s.invoke("storage-disk-get-iter")

    if(out.results_status() == "failed"):
        print (out.results_reason() + "\n")
        sys.exit (2)

    return out.child_get('attributes-list').children_get()

def raw_storage_stats(disks):
    disk_stats = {}

    for disk in disks:
        t = disk.child_get("disk-inventory-info").child_get_string('disk-type')
        c = disk.child_get("disk-inventory-info").child_get_int('capacity-sectors')
        c *= disk.child_get("disk-stats-info").child_get_int('bytes-per-sector')
        owner = disk.child_get("disk-ownership-info").child_get_string('owner-node-name')

        if owner not in disk_stats:
            disk_stats[owner] = {}

        if t not in disk_stats[owner]:
            disk_stats[owner][t] = {}

        if 'raw' not in disk_stats[owner][t]:
            disk_stats[owner][t]['raw'] = c
        else:
            disk_stats[owner][t]['raw'] += c
    return disk_stats

def get_disk_types(disk_stats):
    types = []
    for owner, data in disk_stats.items():
      for t in data:
        if t not in types:
            types.append(t)
    return types

def pretty_tb(b):
    return str(round(b_to_tb(b), 2))

def b_to_tb(b):
    return (float(b)/1000.0/1000.0/1000.0/1000.0)

def print_raw_stats(disk_stats, types):
    print 'Disk Statistics:'
    print 'owner, ' + '_raw, '.join(types) + '_raw'
    for owner, data in disk_stats.items():
        s = owner + ', '
        for t in types:
            if t in data:
                s += str(round(b_to_tb(data[t]['raw']), 2)) + ', '
            else:
                s += '0, '
        s = s.rstrip(' ,')
        print s
    print ''

if __name__ == '__main__':
    main()
