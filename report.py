#!/usr/bin/python
from os import environ
from re import sub as substitute

from allocations import list_merit_allocations
from usage import allocation_cinder_usage, allocation_swift_usage

from swiftclient import client as swiftc

creds = {}

creds['username'] = environ['OS_USERNAME']
creds['password'] = environ['OS_PASSWORD']
creds['tenant_name'] = environ['OS_TENANT_NAME']
creds['auth_url'] = environ['OS_AUTH_URL']
creds['region_name'] = environ['OS_SWIFT_REGION_NAME']
creds['insecure'] = True
#insert here cmd line flag to set insecure true/false


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
#cleanup clients

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

  print tenant.id + ", " + \
        tenant.vicnode_id + ", " + \
        str(swift_usage_info['gb_allocated']) + ", " + \
        str(swift_usage_info['gb_used']) + ", " + \
        str(cinder_usage_info['gb_allocated'])  + ", " + \
        str(cinder_usage_info['gb_used'])  + ", " + \
        str(swift_usage_info['gb_allocated'] + cinder_usage_info['gb_allocated']) + ", " + \
        str(swift_usage_info['gb_used'] + cinder_usage_info['gb_used']) + ", "

print "total, total, " + str(total_allocated_swift) + ", " + str(total_used_swift) + ", " + str(total_allocated_cinder) + ", " + str(total_used_cinder) + ", " + str(total_allocated_swift + total_allocated_cinder) + ", " + str(total_used_swift + total_used_cinder)
