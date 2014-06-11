#!/usr/bin/python
import argparse

from os import environ
from re import sub as substitute

from keystoneclient.v2_0 import client as keystonec
from swiftclient import client as swiftc
from cinderclient import client as cinderc

def main():
  creds = {}

  parser = argparse.ArgumentParser(description='VicNode reporting tool')
  parser.add_argument('-i', '--insecure', action='store_true', help='Whether to connect to endpoints using insecure SSL')
  args = parser.parse_args()

  creds['insecure'] = args.insecure

  creds['username'] = environ['OS_USERNAME']
  creds['password'] = environ['OS_PASSWORD']
  creds['tenant_name'] = environ['OS_TENANT_NAME']
  creds['auth_url'] = environ['OS_AUTH_URL']
  creds['region_name'] = environ['OS_SWIFT_REGION_NAME']
    
  merit_allocations = list_merit_allocations(creds)
  
  total_allocated_cinder = 0
  total_used_cinder = 0
  
  total_allocated_swift = 0
  total_used_swift = 0
  
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
    total_allocated_swift += swift_usage_info['gb_allocated']
    total_used_swift += swift_usage_info['gb_used']
  
    creds['region_name'] = environ['OS_CINDER_REGION_NAME']
    cinder_usage_info = allocation_cinder_usage(creds, tenant.id)
    total_allocated_cinder += cinder_usage_info['gb_allocated']
    total_used_cinder += cinder_usage_info['gb_used']
  
    print ', '.join([tenant.id,
                     tenant.vicnode_id,
                     str(swift_usage_info['gb_allocated']),
                     str(round(swift_usage_info['gb_used'], 2) ),
                     str(cinder_usage_info['gb_allocated']),
                     str(cinder_usage_info['gb_used']),
                     str(swift_usage_info['gb_allocated'] + cinder_usage_info['gb_allocated']),
                     str(swift_usage_info['gb_used'] + cinder_usage_info['gb_used'])])
  
  print ', '.join(['total',
                   'total',
                   str(total_allocated_swift),
                   str(round(total_used_swift)),
                   str(total_allocated_cinder),
                   str(total_used_cinder),
                   str(total_allocated_swift + total_allocated_cinder),
                   str(total_used_swift + total_used_cinder)])

def list_merit_allocations(creds):

  merit_allocation_tenants = []

  client = keystonec.Client(username=creds['username'],
                                  password=creds['password'],
                                  tenant_name=creds['tenant_name'],
                                  insecure=creds['insecure'],
                                  auth_url=creds['auth_url'],
                                  region_name=creds['region_name'])

  return [ tenant for tenant in client.tenants.list() if hasattr(tenant, 'vicnode_id') ]

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

  usage['gb_used'] = usage['gb_allocated']

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

  if 'x-account-meta-account-bytes' in account_info:
    usage['gb_allocated'] = float(account_info['x-account-meta-account-bytes'])/1024/1024/1024
  else:
    usage['gb_allocated'] = float(0)

  usage['gb_used'] = float(account_info['x-account-bytes-used'])/1024/1024/1024

  return usage

if __name__ == '__main__':
  main()
