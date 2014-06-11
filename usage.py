#!/usr/bin/python

from cinderclient import client as cinderc
from swiftclient import client as swiftc

def allocation_cinder_usage(creds, tenant_id):

  usage = {}

  cinder = cinderc.Client('1',
                          creds['username'],
                          creds['password'],
                          project_id=creds['tenant_name'],
                          auth_url=creds['auth_url'],
                          insecure=creds['insecure'],
                          region_name=creds['region_name'])


  quota_info = float(cinder.quotas.get(tenant_id).gigabytes)
  if quota_info > 0:
    usage['gb_allocated'] = float(cinder.quotas.get(tenant_id).gigabytes)
  else:
    usage['gb_allocated'] = float(0)

  usage['gb_used'] = float(0)

  #cleanup clients

  return usage

def allocation_swift_usage(creds, tenant_id, swift_auth_url):

  usage = {}

  swift = swiftc.Connection(authurl=creds['auth_url'],
                            user=creds['username'],
                            key=creds['password'],
                            tenant_name=creds['tenant_name'],
                            insecure=creds['insecure'],
                            os_options={'region_name': creds['region_name'],
                                        'object_storage_url': swift_auth_url + tenant_id},
                            auth_version='2.0')

  account_info = swift.head_account()

  #round dis
  if 'x-account-meta-account-bytes' in account_info:
    usage['gb_allocated'] = float(account_info['x-account-meta-account-bytes'])/1024/1024/1024
  else:
    usage['gb_allocated'] = float(0)

  #round dis
  usage['gb_used'] = float(account_info['x-account-bytes-used'])/1024/1024/1024

  #cleanup clients

  return usage
