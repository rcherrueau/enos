# -*- coding: utf-8 -*-
from provider import Provider
from host import Host

import logging

import subprocess
import sys
import netifaces as net

class Ovh(Provider):
    def init(self, config, force=False):
        def _cmd(cmd):
            logging.info(cmd)
            subprocess.check_call(cmd)

        def _find_nic_of(ip):
            nic = 'lo'

            for nic in net.interfaces():
                for inet in net.ifaddresses(nic)[net.AF_INET]:
                    if inet['addr'] == ip:
                        return nic

            return nic

        def _make_hosts(resource):
            """Builds Host objects for `resource`.

            A `resource` can be either (i) a dict with Host entries,
            or (ii) a list of Host entries.
            """
            if isinstance(resource, list):
                return sum(map(_make_hosts, resource), [])
            else:
                return [Host(address=resource['address'],
                             alias=resource.get('alias', None),
                             user=resource.get('user', None),
                             keyfile=resource.get('keyfile', None),
                             port=resource.get('port', None),
                             extra=resource.get('extra', {}))]

        # Get IP of control_compute and compute node
        control_compute_ip = config['resources']['os_control_compute']
        compute_ip = config['resources']['os_compute']

        # DNAT for horizon
        control_compute_ip_public = net.ifaddresses('ens3')[net.AF_INET][0]['addr']
        dnat_cmd = "sudo iptables -t nat -A PREROUTING --dst %s -p tcp --dport 80 -j DNAT --to-destination %s" % (
                control_compute_ip_public, 
                control_compute_ip)
        _cmd(dnat_cmd)

        # SNAT for vrack VM internet traffic 
        snat_cmd = "sudo iptables -t nat -A POSTROUTING -o ens3 -j MASQUERAD"
        _cmd(snat_cmd)

        # Fallback to static configuration
        config['resources'] = {
            'control': {
                'address': control_compute_ip,
                'alias': 'control_compute',
                'user': 'debian',
                'extra': {'ansible_become': True}
            },
            'network': {
                'address': control_compute_ip,
                'alias': 'control_compute',
                'user': 'debian',
                'extra': {'ansible_become': True}
            },
            'compute': [
                # {
                #     'address': control_compute_ip,
                #     'alias': 'control_compute',
                #     'user': 'debian',
                #     'extra': {'ansible_become': True}
                # },
                {
                    'address': compute_ip,
                    'alias': 'compute',
                    'user': 'debian',
                    'extra': {'ansible_become': True}
                }
            ]
        }

        vrack_nic = _find_nic_of(control_compute_ip)
        eths = [vrack_nic, vrack_nic]
        roles = {r: _make_hosts(vs) for (r, vs) in config['resources'].items()}

        return (roles, eths)

    def destroy(self, env):
        logging.warning('Resource destruction is not implemented '
                        'for the static provider. Call `enos destroy` '
                        '(without --hard) to delete OpenStack containers.')

    def default_config(self):
        return {
            'eths': [ 'ens4', 'ens4' ]
        }

    def topology_to_resources(self, topology):
        resources = {}

        for grp, rsc in topology.items():
            self._update(resources, rsc)
            resources.update({grp: rsc.values()})

        return resources

    def _update(self, rsc1, rsc2):
        "Update `rsc1` by pushing element from `rsc2`"
        for k, v in rsc2.items():
            values = rsc1.setdefault(k, [])
            values.append(v)
