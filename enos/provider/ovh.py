# -*- coding: utf-8 -*-
from provider import Provider
from host import Host

import logging

import subprocess
import sys
import netifaces as net

class Ovh(Provider):
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

        # Get IP of control_compute and compute node
        control_compute_ip = config['resources']['control_compute']
        compute_ip = config['resources']['compute']

        # Make a fake interface for public net. See veth0 and veth1
        # as two interfaces linked. To delete theme:
        # sudo ip link delete veth0 type veth peer name veth1
        ssh_cmd = 'ip link show veth0 || sudo ip link add veth0 type veth peer name veth1'
        for host in [ control_compute_ip, compute_ip ]:
            ssh = subprocess.Popen(["ssh", "%s" % host, ssh_cmd],
                                   shell=False,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)

            res = ssh.stdout.readlines()
            if not res:
                logging.error(ssh.stderr.readlines())
            else:
                logging.info(res)

        # DNAT for horizon
        # control_private_ip = net.ifaddresses('ens4')[net.AF_INET][0]['addr']
        control_compute_private_ip = '192.168.0.249'
        dnat_cmd = "sudo iptables -t nat -A PREROUTING --dst %s ",
                   "-p tcp --dport 80 -j DNAT --to-destination %s"
                   % (control_compute_ip, control_compute_private_ip)
        subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        res = ssh.stdout.readlines()
        if not res:
            logging.error(ssh.stderr.readlines())
        else:
            logging.info(res)


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

        eths = config['provider']['eths']
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
