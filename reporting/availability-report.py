#!/usr/bin/env python

import os
import calendar
import requests
import cssselect
import lxml.etree
import datetime
import pprint

from jinja2 import Environment, FileSystemLoader
from ConfigParser import SafeConfigParser

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, SUPPRESS

AVAILABILITY_URL = "/cgi-bin/avail.cgi?t1=%s&t2=%s&show_log_entries=&host=%s&assumeinitialstates=yes&assumestateretention=yes&assumestatesduringnotrunning=yes&includesoftstates=yes&initialassumedhoststate=3&initialassumedservicestate=6&timeperiod=[+Current+time+range+]&backtrack=4"

SERVICE_NAMES = {'snapmirror_health': 'SnapMirror',
                 'aggregate_health': 'Aggregate',
                 'cluster_health': 'Cluster',
                 'disk_health': 'Disk',
                 'filer_hardware_health': 'Hardware',
                 'interface_health': 'Interface',
                 'netapp_alarms': 'Alarms',
                 'port_health': 'Port',
                 'volume_health': 'Volume',
                 'snapshot_health': 'Snapshot',
                 'check_all_disks': 'Disk',
                 'check_swift': 'Object Store',
                 'Average': 'Average'}


def parse_service_availability(service):
    service, ok, warn, unknown, crit, undet = service.getchildren()
    service_name = ''.join([t for t in service.itertext()])
    if service_name in SERVICE_NAMES:
        name = SERVICE_NAMES[service_name] + ' availability'

        return {'name': name,
                'ok': ok.text.split(' ')[0].rjust(8),
                'warning': warn.text.split(' ')[0].rjust(8),
                'unknown': unknown.text.split(' ')[0].rjust(8),
                'critical': crit.text.split(' ')[0].rjust(8)}


def parse_availability(html, host):
    tr = cssselect.GenericTranslator()
    h = lxml.etree.HTML(html)
    table = None
    for i, e in enumerate(h.xpath(tr.css_to_xpath('.dataTitle')), -1):
        if 'State Breakdowns For Host Services:' not in e.text:
            continue
        table = h.xpath(tr.css_to_xpath('table.data'))[i]
        break
    services = []
    if table is not None:
        for row in table.xpath(tr.css_to_xpath('tr.dataOdd, tr.dataEven')):
            service = parse_service_availability(row)
            if service is not None:
                services.append(service)

    context = {host: services}
    return context


def gm_timestamp(datetime_object):
    return calendar.timegm(datetime_object.utctimetuple())


def get_availability(nagios_url, start_date, end_date, host):

    url = AVAILABILITY_URL % (gm_timestamp(start_date),
                              gm_timestamp(end_date),
                              host)
    url = nagios_url + url
    resp = requests.get(url)
    return parse_availability(resp.text, host)


def render_template(data):

    env = Environment(loader=FileSystemLoader('templates'), lstrip_blocks=True)
    text = env.get_template('availability.tmpl')
    text = text.render({'data': data})
    return text


def collect_args():

    parser = ArgumentParser(argument_default=SUPPRESS,
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-u', '--nagios_url', action='store',
                        help='Nagios URL')
    parser.add_argument('-n', '--hosts', action='append',
                        help='Hosts to generate reports for')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Enable debug')
    conf = os.path.join(os.getcwd(), 'availability-report.conf')
    parser.add_argument('-c', '--config', default=conf,
                        help='Path to configuration file')

    return parser


def parse_config(section, filename):
    """Read configuration settings from config file"""

    options = {}
    config_file = filename

    if not os.path.exists(config_file):
        print 'Warning %s not found...' % config_file
    parser = SafeConfigParser()
    parser.read(config_file)
    for name, value in parser.items(section):
        options[name] = value

    options['hosts'] = options['hosts'].split(',') if 'hosts' in options else []
    options['debug'] = True if options.get('debug') == 'True' else False

    return options


if __name__ == '__main__':

    hosts = []
    nagios_url = None

    parser = collect_args()
    args = parser.parse_args()

    options = parse_config('main', args.config)
    parser.set_defaults(**options)

    args = parser.parse_args()

    if 'nagios_url' in args:
        nagios_url = args.nagios_url
    if 'hosts' in args:
        hosts = args.hosts
    if 'debug' in args:
        debug = args.debug

    now = datetime.datetime.now()
    then = now - datetime.timedelta(days=7)

    if nagios_url is None:
        parser.error('nagios_url not defined')

    if len(hosts) == 0:
        parser.error('hosts not specified')

    for host in hosts:
        data = get_availability(nagios_url, now, then, host)
        if debug:
            pprint.pprint(data)
        print render_template(data)
