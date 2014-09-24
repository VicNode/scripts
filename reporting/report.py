#!/usr/bin/python
# Copyright (C) 2014 Aptira <info@aptira.com>
#
# Author: Michael Chapman   <michael@aptira.com>
# Author: Sina Sadeghi      <sina@aptira.com>


import argparse
import sys
sys.path.append('./NetApp/lib/python/NetApp')
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

    parser_netapp = subparsers.add_parser('netapp', help='Netapp Statistics Reporting')
    parser_netapp.add_argument('-c', '--cluster', required=True, help='Netapp cluster address or hostname')
    parser_netapp.add_argument('-u', '--username', required=True, help='NetApp cluster username')
    parser_netapp.add_argument('-p', '--password', required=True, help='Netapp cluster password')
    parser_netapp.set_defaults(func=report_netapp)

    args = parser.parse_args()
    args.func(args)


def report_allocation(args):
    creds = {}
    creds['insecure'] = args.insecure

    if args.username is None:
        if 'OS_USERNAME' not in environ:
            print 'OpenStack username environment variable OS_USERNAME not set and -u not used'
            sys.exit(1)
        else:
            creds['username'] = environ['OS_USERNAME']
    else:
        creds['username'] = args.username

    if args.password is None:
        if 'OS_PASSWORD' not in environ:
            print 'OpenStack password environment variable OS_PASSWORD not set and -p not used'
            sys.exit(1)
        else:
            creds['password'] = environ['OS_PASSWORD']
    else:
        creds['password'] = args.password

    if args.tenant is None:
        if 'OS_TENANT_NAME' not in environ:
            print 'OpenStack tenant name environment variable OS_TENANT_NAME not set and -t not used'
            sys.exit(1)
        else:
            creds['tenant_name'] = environ['OS_TENANT_NAME']
    else:
        creds['tenant_name'] = args.tenant

    if args.auth_url is None:
        if 'OS_AUTH_URL' not in environ:
            print 'OpenStack auth url environment variable OS_AUTH_URL not set and -a not used'
            sys.exit(1)
        else:
            creds['auth_url'] = environ['OS_AUTH_URL']
    else:
        creds['auth_url'] = args.auth_url

    if args.swift_region is None:
        if 'OS_SWIFT_REGION_NAME' not in environ:
            print 'OpenStack swift region name environment variable OS_SWIFT_REGION_NAME not set and -s not used'
            sys.exit(1)
        else:
            creds['swift_region_name'] = environ['OS_SWIFT_REGION_NAME']
    else:
        creds['swift_region_name'] = args.swift_region

    if args.cinder_region is None:
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
    swift_auth_url = re.sub('AUTH_.*', 'AUTH_', swift.url)

    print 'tenant_id, vicnode_id, swift_quota, swift_used, cinder_quota, cinder_used, total_allocation_quota, total_allocation_used'

    for tenant in merit_allocations:

        # creds['region_name'] = environ['OS_SWIFT_REGION_NAME']
        swift_usage_info = allocation_swift_usage(creds, tenant.id, swift_auth_url)

        # creds['region_name'] = environ['OS_CINDER_REGION_NAME']
        cinder_usage_info = allocation_cinder_usage(creds, tenant.id)

        print ', '.join([tenant.id,
                         tenant.vicnode_id,
                         str(swift_usage_info['gb_allocated']),
                         str(round(swift_usage_info['gb_used'], 2)),
                         str(cinder_usage_info['gb_allocated']),
                         str(cinder_usage_info['gb_used']),
                         str(swift_usage_info['gb_allocated'] + cinder_usage_info['gb_allocated']),
                         str(swift_usage_info['gb_used'] + cinder_usage_info['gb_used'])])


def list_merit_allocations(creds):

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

    return [tenant for tenant in client.tenants.list() if hasattr(tenant, 'vicnode_id')]


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
        usage['gb_allocated'] = float(account_info['x-account-meta-account-bytes']) / 1024 / 1024 / 1024
    else:
        usage['gb_allocated'] = float(0)

    usage['gb_used'] = float(account_info['x-account-bytes-used']) / 1024 / 1024 / 1024

    return usage


def report_netapp(args):
    conn = connect(args.cluster, args.username, args.password)
    print

    disks = get_disks(conn)
    aggrs = get_aggrs(conn)
    volumes = get_volumes(conn)
    vservers = get_vservers(conn)

    report_disks(disks)
    report_aggregates(aggrs)
    report_volumes(volumes)
    report_vservers(vservers, volumes)


def report_disks(disks):
    disk_stats = get_disk_stats(disks)
    disk_types = get_disk_types(disk_stats)
    print_disk_stats(disk_stats, disk_types)


def report_volumes(volumes):
    print_volume_stats(volumes)


def report_aggregates(aggrs):
    aggr_stats = get_aggr_stats(aggrs)
    print_aggr_stats(aggr_stats)


def report_vservers(vservers, volumes):
    vserver_stats = get_vserver_stats(vservers, volumes)
    print_vserver_stats(vserver_stats)


def connect(cluster, user, pw):
    """ Initialise NetApp cluster connection and return connection object """

    conn = NaServer(cluster, 1, 3)
    response = conn.set_style('LOGIN')
    if (response and response.results_errno() != 0):
        resp = response.results_reason()
        print ('Unable to set authentication style %s' % resp)
        sys.exit(2)

    conn.set_admin_user(user, pw)
    response = conn.set_transport_type('HTTP')
    if (response and response.results_errno() != 0):
        resp = response.results_reason()
        print ('Unable to set HTTP transport %s' % resp)
        sys.exit(2)

    return conn


def get_aggrs(conn):
    """ Return a list of all aggregates in the cluster """
    out = conn.invoke('aggr-get-iter')

    if(out.results_status() == 'failed'):
        print (out.results_reason() + '\n')
        sys.exit(2)

    return out.child_get('attributes-list').children_get()


def get_aggr_stats(aggrs):
    stats = {}

    for aggr in aggrs:
        name = aggr.child_get_string('aggregate-name')
        ownership_attrs = aggr.child_get('aggr-ownership-attributes')
        owner = ownership_attrs.child_get_string('owner-name')

        aggr_space_attrs = aggr.child_get('aggr-space-attributes')
        available = aggr_space_attrs.child_get_string('size-available')
        total = aggr_space_attrs.child_get_string('size-total')
        used = aggr_space_attrs.child_get_string('size-used')

        if owner not in stats:
            stats[owner] = [{'name': name, 'available': available,
                             'total': total, 'used': used}]
        else:
            stats[owner].append({'name': name, 'available': available,
                                 'total': total, 'used': used})
    return stats


def print_aggr_stats(aggr_stats):
    print 'Aggregate Statistics:'
    print ', '.join(['controller', 'aggregate', 'total', 'used', 'available'])
    for owner, data in aggr_stats.items():
        for item in data:
            name = item['name']
            total = pretty_tb(item['total'])
            used = pretty_tb(item['used'])
            available = pretty_tb(item['available'])
            print ', '.join([owner, name, total, used, available])
    print


def get_vservers(conn):
    """ Return a list of all data vservers in the cluster """
    out = conn.invoke('vserver-get-iter')

    if(out.results_status() == 'failed'):
        print (out.results_reason() + '\n')
        sys.exit(2)

    attributes = out.child_get('attributes-list')
    servers = attributes.children_get()

    return [server for server in servers if server.child_get_string('vserver-type') == 'data']


def get_vserver_stats(servers, volumes):
    stats = {}

    for volume in volumes:
        vol_id_attrs = volume.child_get('volume-id-attributes')
        vol_space_attrs = volume.child_get('volume-space-attributes')
        vserver = vol_id_attrs.child_get_string('owning-vserver-name')
        name = vol_id_attrs.child_get_string('name')

        if vserver.startswith('os_') and name.find('rootvol') != 0:
            total = vol_space_attrs.child_get_int('size-total')
            used = vol_space_attrs.child_get_int('size-used')
            available = vol_space_attrs.child_get_int('size-available')
            if vserver not in stats:
                stats[vserver] = {'volume_count': 1, 'total': total,
                                  'used': used, 'available': available}
            else:
                stats[vserver]['total'] += total
                stats[vserver]['used'] += used
                stats[vserver]['available'] += available
                stats[vserver]['volume_count'] += 1

    return stats


def print_vserver_stats(vserver_stats):
    print 'VServer Statistics:'
    print ', '.join(['vserver', 'total', 'used', 'available', 'volume_count'])
    for vserver, data in vserver_stats.items():
        total = pretty_tb(data['total'])
        used = pretty_tb(data['used'])
        available = pretty_tb(data['available'])
        vol_count = str(data['volume_count'])
        print ', '.join([vserver, total, used, available, vol_count])
    print


def get_volumes(conn):
    cmd = NaElement('volume-get-iter')
    cmd.child_add_string('max-records', 500)
    out = conn.invoke_elem(cmd)

    if(out.results_status() == 'failed'):
        print (out.results_reason() + '\n')
        sys.exit(2)

    attributes = out.child_get('attributes-list')

    return attributes.children_get()


def print_volume_stats(volumes):
    print 'Volume Statistics:'
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
            print ', '.join([name, vserver, aggr, pretty_tb(total),
                             pretty_tb(used), pretty_tb(available)])
    print


def get_disks(conn):
    """ Return a list of all disks in the cluster """
    out = conn.invoke('storage-disk-get-iter')

    if(out.results_status() == 'failed'):
        print (out.results_reason() + '\n')
        sys.exit(2)

    return out.child_get('attributes-list').children_get()


def get_disk_stats(disks):
    stats = {}

    for disk in disks:
        disk_inventory = disk.child_get('disk-inventory-info')
        disk_stats = disk.child_get('disk-stats-info')
        disk_ownership = disk.child_get('disk-ownership-info')
        disk_type = disk_inventory.child_get_string('disk-type')
        sectors = disk_inventory.child_get_int('capacity-sectors')
        bytes_per_sector = disk_stats.child_get_int('bytes-per-sector')
        capacity = sectors * bytes_per_sector
        owner = disk_ownership.child_get_string('owner-node-name')

        if owner not in stats:
            stats[owner] = {}

        if disk_type not in stats[owner]:
            stats[owner][disk_type] = {}

        if 'capacity' not in stats[owner][disk_type]:
            stats[owner][disk_type]['capacity'] = capacity
        else:
            stats[owner][disk_type]['capacity'] += capacity

    return stats


def get_disk_types(disk_stats):
    """ Return a list of all disks from the disk_stats """
    disk_types = []

    for owner, data in disk_stats.items():
        for disk_type in data:
            if disk_type not in disk_types:
                disk_types.append(disk_type)

    return disk_types


def pretty_tb(b):
    return str(round(b_to_tb(b), 2))


def b_to_tb(b):
    return (float(b) / 1024.0 / 1024.0 / 1024.0 / 1024.0)


def print_disk_stats(disk_stats, disk_types):
    print 'Disk Statistics:'
    print 'controller, ' + ', '.join(disk_types)

    for owner, data in disk_stats.items():
        output = owner
        for disk_type in disk_types:
            output += ', '
            if disk_type in data:
                output += pretty_tb(data[disk_type]['capacity'])
            else:
                output += '0'
        print output
    print


if __name__ == '__main__':
    main()
