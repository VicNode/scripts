#!/usr/bin/python
#
# Copyright (c) 2014 Aptira <info@aptira.com>
# Copyright (c) 2014 University of Melbourne
#
# Author: Michael Chapman   <michael@aptira.com>
# Author: Sina Sadeghi      <sina@aptira.com>
# Author: Marcus Furlong    <furlongm@gmail.com>

import os
import sys
import argparse

sys.path.append('./NetApp/lib/python/NetApp')
from NaServer import NaServer
from NaElement import NaElement

from keystoneclient.v2_0 import client as ks_client
from keystoneclient.exceptions import AuthorizationFailure, NotFound
from swiftclient.exceptions import ClientException
from swiftclient import client as swiftclient
from cinderclient import client as cinderclient

SWIFT_QUOTA_KEY = 'X-Account-Meta-Quota-Bytes'.lower()


def main():
    parser = argparse.ArgumentParser(description='VicNode Usage Report Tool')
    parser.add_argument('-c', '--clusters', required=True, nargs='+',
                        help='Netapp cluster IP addresses or hostnames')
    parser.add_argument('-u', '--username', required=True,
                        help='NetApp cluster username')
    parser.add_argument('-p', '--password', required=True,
                        help='Netapp cluster password')

    args = parser.parse_args()
    tenants = get_vicnode_tenants()
    get_netapp_stats(tenants, args)
    get_openstack_stats(tenants)


def get_netapp_stats(tenants, args):
    for cluster in args.clusters:
        conn = netapp_connect(cluster, args.username, args.password)

        disks = get_disks(conn)
        aggrs = get_aggrs(conn)
        volumes = get_volumes(conn)
        vservers = get_vservers(conn)

        report_disks(cluster, disks)
        report_aggregates(cluster, aggrs)
        report_volumes(cluster, volumes, tenants)
        report_vservers(cluster, vservers, volumes, tenants)


def get_openstack_stats(tenants):
    kc = get_keystone_client()
    token = kc.auth_token
    catalog = kc.service_catalog
    swift_url = catalog.url_for(service_type='object-store',
                                endpoint_type='adminURL',
                                region_name='VicNode')

    print 'Vault and Compute Statistics (GB)'
    print ', '.join(['tenant', 'vicnode_id', 'tenant_id',
                     'vault_quota', 'vault_used',
                     'compute_quota', 'compute_used'])

    for key, tenant in tenants.iteritems():

        tenant_url = swift_url + 'AUTH_' + tenant.id
        swift_usage = get_swift_usage(tenant_url, token)
        cinder_usage = get_cinder_usage(tenant.id)

        print ', '.join([tenant.name,
                         tenant.vicnode_id,
                         tenant.id,
                         pretty_gb(swift_usage['gb_allocated']),
                         pretty_gb(swift_usage['gb_used']),
                         pretty_gb(cinder_usage['gb_allocated']),
                         pretty_gb(cinder_usage['gb_used'])])


def get_cinder_usage(tenant_id):
    usage = {}
    cc = get_cinder_client()
    quota = cc.quotas.get(tenant_id).gigabytes
    usage['gb_allocated'] = usage['gb_used'] = quota

    return usage


def get_swift_usage(tenant_url, token):
    usage = {}
    usage['gb_allocated'] = usage['gb_used'] = 0

    try:
        swift_account = swiftclient.head_account(url=tenant_url, token=token)

        if SWIFT_QUOTA_KEY in swift_account:
            usage['gb_allocated'] = b_to_gb(swift_account[SWIFT_QUOTA_KEY])
        usage['gb_used'] = b_to_gb(swift_account['x-account-bytes-used'])
    except ClientException:
        pass

    return usage


def get_cinder_client():
    auth_username = os.environ.get('OS_USERNAME')
    auth_password = os.environ.get('OS_PASSWORD')
    auth_tenant = os.environ.get('OS_TENANT_NAME')
    auth_url = os.environ.get('OS_AUTH_URL')
    auth_cacert = os.environ.get('OS_CACERT')

    cc = cinderclient.Client('1', auth_username,
                             auth_password,
                             auth_tenant,
                             auth_url,
                             cacert=auth_cacert)
    return cc


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


def get_vicnode_tenants():
    tenants = {}
    kc = get_keystone_client()
    for tenant in kc.tenants.list():
        if hasattr(tenant, 'vicnode_id'):
            tenants[tenant.id] = tenant

    return tenants


def get_tenant(name_or_id):
    kc = get_keystone_client()
    try:
        tenant = kc.tenants.get(name_or_id)
    except NotFound:
        tenant = kc.tenants.find(name=name_or_id)
    return tenant


def get_vicnode_id(tenants, tenant_id):
    if tenant_id in tenants:
        vicnode_id = tenants[tenant_id].vicnode_id
    else:
        vicnode_id = 'Unknown'

    return vicnode_id


def get_tenant_name(tenants, tenant_id):
    if tenant_id in tenants:
        tenant_name = tenants[tenant_id].name
    else:
        tenant_name = get_tenant(tenant_id).name

    return tenant_name


def report_disks(cluster, disks):
    disk_stats = get_disk_stats(disks)
    disk_types = get_disk_types(disk_stats)
    print_disk_stats(cluster, disk_stats, disk_types)


def report_volumes(cluster, volumes, tenants):
    print_volume_stats(cluster, volumes, tenants)


def report_aggregates(cluster, aggrs):
    aggr_stats = get_aggr_stats(aggrs)
    print_aggr_stats(cluster, aggr_stats)


def report_vservers(cluster, vservers, volumes, tenants):
    vserver_stats = get_vserver_stats(vservers, volumes)
    print_vserver_stats(cluster, vserver_stats, tenants)


def netapp_connect(cluster, user, pw):
    """Initialise NetApp cluster connection and return connection object"""
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


def print_aggr_stats(cluster, aggr_stats):
    print 'Aggregate Statistics - %s' % cluster
    print ', '.join(['controller', 'aggregate', 'total', 'used', 'free'])
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

    return [server for server in servers
            if server.child_get_string('vserver-type') == 'data']


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


def print_vserver_stats(cluster, vserver_stats, tenants):
    print 'Market VServer Statistics (TB) - %s' % cluster
    print ', '.join(['tenant', 'vicnode_id', 'vserver',
                     'total', 'used', 'free', 'volume_count'])

    for vserver, data in vserver_stats.items():
        tenant_id = vserver.split('_')[1]
        vicnode_id = get_vicnode_id(tenants, tenant_id)
        tenant_name = get_tenant_name(tenants, tenant_id)
        total = pretty_tb(data['total'])
        used = pretty_tb(data['used'])
        available = pretty_tb(data['available'])
        vol_count = str(data['volume_count'])
        print ', '.join([tenant_name,
                         vicnode_id,
                         vserver,
                         total,
                         used,
                         available,
                         vol_count])
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


def print_volume_stats(cluster, volumes, tenants):
    print 'Market Volume Statistics (TB) - %s' % cluster
    print ', '.join(['tenant', 'vicnode_id', 'name', 'vserver', 'aggr',
                     'total', 'used', 'free'])

    for volume in volumes:
        vol_id_attrs = volume.child_get('volume-id-attributes')
        vol_space_attrs = volume.child_get('volume-space-attributes')
        vserver = vol_id_attrs.child_get_string('owning-vserver-name')
        name = vol_id_attrs.child_get_string('name')

        if vserver.startswith('os_') and name.find('rootvol') != 0:
            tenant_id = vserver.split('_')[1]
            vicnode_id = get_vicnode_id(tenants, tenant_id)
            tenant_name = get_tenant_name(tenants, tenant_id)
            aggr = vol_id_attrs.child_get_string('containing-aggregate-name')
            total = vol_space_attrs.child_get_string('size-total')
            used = vol_space_attrs.child_get_string('size-used')
            available = vol_space_attrs.child_get_string('size-available')
            print ', '.join([tenant_name,
                             vicnode_id,
                             name,
                             vserver,
                             aggr,
                             pretty_tb(total),
                             pretty_tb(used),
                             pretty_tb(available)])
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


def print_disk_stats(cluster, disk_stats, disk_types):
    print 'Disk Statistics - %s' % cluster
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


def pretty_gb(gb):
    return str(round(gb, 3))


def b_to_gb(b):
    return (float(b) / 1024.0 / 1024.0 / 1024.0)


def pretty_tb(b):
    return str(round(b_to_tb(b), 3))


def b_to_tb(b):
    return (float(b) / 1024.0 / 1024.0 / 1024.0 / 1024.0)


if __name__ == '__main__':
    main()
