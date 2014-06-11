#!/usr/bin/python

from keystoneclient.v2_0 import client as keystone_client
import copy

def list_merit_allocations(creds):

  merit_allocation_tenants = []

  client = keystone_client.Client(username=creds['username'],
                                  password=creds['password'],
                                  tenant_name=creds['tenant_name'],
                                  insecure=creds['insecure'],
                                  auth_url=creds['auth_url'],
                                  region_name=creds['region_name'])

  return [ tenant for tenant in client.tenants.list() if hasattr(tenant, 'vicnode_id') ]
