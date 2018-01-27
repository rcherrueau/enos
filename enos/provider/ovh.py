# -*- coding: utf-8 -*-
from provider import Provider
from host import Host

import logging

import subprocess
import sys

class OVH(Provider):
    def init(self, config, force=False):
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

        control_compute_ip = config['resources']['control_compute']
        compute_ip = config['resources']['compute']


        # TODO: Make a fake interface for public net on every host
        # reduce(list.__add__,
        #        map(lambda _, vs: _make_hosts(vs),
        #            config['resources'].items()))
        cmd = 'ip link show veth0 || ip link add type veth peer'
        for host in [ control_compute_ip, compute_ip ]:
            ssh = subprocess.Popen(["ssh", "%s" % host.address, cmd],
                                   shell=False,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)

            if ssh.stdout.readlines() == []:
                logging.error(ssh.stderr.readlines())


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
                {
                    'address': control_compute_ip,
                    'alias': 'control_compute',
                    'user': 'debian',
                    'extra': {'ansible_become': True}
                },
                {
                    'address': compute_ip,
                    'alias': 'compute',
                    'user': 'debian',
                    'extra': {'ansible_become': True}
                }
            ]
        }

        eths = [ 'ens4', 'veth0' ]
        roles = {r: _make_hosts(vs) for (r, vs) in config['resources'].items()}

        return (roles, eths)

    def destroy(self, env):
        logging.warning('Resource destruction is not implemented '
                        'for the static provider. Call `enos destroy` '
                        '(without --hard) to delete OpenStack containers.')

    def default_config(self):
        return {
            'eths':    None   # A pair that contains the name of
                              # network and external interfaces
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
