# -*- coding: utf-8 -*-
# Copyright (c) 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Playbook plugin for Remove NFS Gateway host."""


from decapod_common import log
from decapod_common import playbook_plugin
from decapod_common import playbook_plugin_hints


DESCRIPTION = "Remove NFS Gateway host"
"""Plugin description."""

HINTS_SCHEMA = {
    "remove_rgw": {
        "description": "Remove RGW on these nodes as well",
        "typename": "boolean",
        "type": "boolean",
        "default_value": False
    },
    "remove_nfs_rgw_user": {
        "description": "Remove NFS user from Rados Gateway",
        "typename": "boolean",
        "type": "boolean",
        "default_value": False
    }
}
"""Schema for playbook hints."""

LOG = log.getLogger(__name__)
"""Logger."""


class RemoveNfs(playbook_plugin.CephAnsiblePlaybook):

    NAME = "Remove NFS Gateway host"
    DESCRIPTION = DESCRIPTION
    PUBLIC = True
    REQUIRED_SERVER_LIST = True
    SERVER_LIST_POLICY = playbook_plugin.ServerListPolicy.in_this_cluster
    HINTS = playbook_plugin_hints.Hints(HINTS_SCHEMA)

    def on_post_execute(self, task, exc_value, exc_type, exc_tb):
        super().on_post_execute(task, exc_value, exc_type, exc_tb)

        if exc_value:
            LOG.warning("Cannot remove NFS gateway host: %s (%s)",
                        exc_value, exc_type)
            raise exc_value

        playbook_config = self.get_playbook_configuration(task)
        config = playbook_config.configuration["inventory"]
        cluster = playbook_config.cluster
        servers = playbook_config.servers
        servers = {srv.ip: srv for srv in servers}

        nfs_servers = config.pop("nfss")
        nfs_servers = [servers[ip] for ip in nfs_servers]
        cluster.remove_servers(nfs_servers, "nfss")

        rgw_servers = config.pop("rgws", [])
        if rgw_servers:
            rgw_servers = [servers[ip] for ip in rgw_servers]
            cluster.remove_servers(rgw_servers, "rgws")

        if cluster.configuration.changed:
            cluster.save()

    def make_playbook_configuration(self, cluster, servers, hints):
        global_vars = self.make_global_vars(cluster, servers, hints)
        inventory = self.make_inventory(cluster, servers, hints)

        return global_vars, inventory

    def make_global_vars(self, cluster, servers, hints):
        result = super().make_global_vars(cluster, servers, hints)

        return {
            "cluster": result["cluster"],
            "ceph_nfs_rgw_user": result["ceph_nfs_rgw_user"],
            "remove_nfs_rgw_user": bool(hints["remove_nfs_rgw_user"])
        }

    def make_inventory(self, cluster, servers, hints):
        groups = {"nfss": servers}
        if hints["remove_rgw"]:
            groups["rgws"] = servers

        inventory = {"_meta": {"hostvars": {}}}

        for name, group_servers in groups.items():
            for srv in group_servers:
                inventory.setdefault(name, []).append(srv.ip)

                hostvars = inventory["_meta"]["hostvars"].setdefault(
                    srv.ip, {})
                hostvars["ansible_user"] = srv.username

        return inventory
