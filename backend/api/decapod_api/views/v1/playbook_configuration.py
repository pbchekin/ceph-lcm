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
"""This module contains view for /v1/playbook_configuration API."""


from decapod_api import auth
from decapod_api import exceptions as http_exceptions
from decapod_api import validators
from decapod_api.views import generic
from decapod_common import exceptions as base_exceptions
from decapod_common import log
from decapod_common import plugins
from decapod_common.models import cluster
from decapod_common.models import playbook_configuration
from decapod_common.models import server


DATA_SCHEMA = {
    "name": {"$ref": "#/definitions/non_empty_string"},
    "playbook_id": {"$ref": "#/definitions/non_empty_string"},
    "cluster_id": {"$ref": "#/definitions/uuid4"},
    "configuration": {"type": "object"}
}
"""Data schema for the model."""

MODEL_SCHEMA = validators.create_model_schema(
    playbook_configuration.PlaybookConfigurationModel.MODEL_NAME,
    DATA_SCHEMA
)
"""Schema for the model with optional data fields."""

POST_SCHEMA = {
    "name": {"$ref": "#/definitions/non_empty_string"},
    "cluster_id": {"$ref": "#/definitions/uuid4"},
    "playbook_id": {"$ref": "#/definitions/non_empty_string"},
    "server_ids": {"$ref": "#/definitions/dmidecode_uuid_array"},
    "hints": {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["id", "value"],
            "additionalProperties": False,
            "properties": {
                "id": {"$ref": "#/definitions/non_empty_string"},
                "value": {
                    "oneOf": [
                        {"$ref": "#/definitions/non_empty_string"},
                        {"$ref": "#/definitions/positive_integer"},
                        {"type": "boolean"},
                        {"type": "array"}
                    ]
                }
            }
        }
    }
}
POST_SCHEMA = validators.create_data_schema(POST_SCHEMA, True)
"""Schema for the creating new playbook configuration."""

LOG = log.getLogger(__name__)
"""Logger."""


class PlaybookConfigurationView(generic.VersionedCRUDView):
    """Implementation of view for /v1/playbook_configuration API."""

    decorators = [
        auth.AUTH.require_authorization("api", "view_playbook_configuration"),
        auth.AUTH.require_authentication
    ]

    NAME = "playbook_configuration"
    MODEL_NAME = "playbook_configuration"
    ENDPOINT = "/playbook_configuration/"
    PARAMETER_TYPE = "uuid"

    def get_all(self):
        return playbook_configuration.PlaybookConfigurationModel.list_models(
            self.pagination
        )

    @validators.with_model(playbook_configuration.PlaybookConfigurationModel)
    def get_item(self, item_id, item, *args):
        return item

    @auth.AUTH.require_authorization(
        "api", "view_playbook_configuration_version")
    def get_versions(self, item_id):
        return playbook_configuration.PlaybookConfigurationModel.list_versions(
            str(item_id), self.pagination
        )

    @auth.AUTH.require_authorization(
        "api", "view_playbook_configuration_version")
    def get_version(self, item_id, version):
        model = playbook_configuration.PlaybookConfigurationModel.find_version(
            str(item_id), int(version)
        )

        if not model:
            LOG.info("Cannot find model with ID %s", item_id)
            raise http_exceptions.NotFound

        return model

    @auth.AUTH.require_authorization("api", "edit_playbook_configuration")
    @validators.with_model(playbook_configuration.PlaybookConfigurationModel)
    @validators.require_schema(MODEL_SCHEMA)
    @validators.no_updates_on_default_fields
    def put(self, item_id, item):
        for fieldname in "configuration", "name":
            if fieldname in self.request_json["data"]:
                setattr(item, fieldname, self.request_json["data"][fieldname])

        item.initiator_id = self.initiator_id

        try:
            item.save()
        except base_exceptions.CannotUpdateDeletedModel as exc:
            LOG.warning(
                "Cannot update playbook configuration %s (deleted at %s, "
                "version %s)",
                item_id, item.time_deleted, item.version
            )
            raise http_exceptions.CannotUpdateDeletedModel() from exc
        except base_exceptions.UniqueConstraintViolationError as exc:
            LOG.warning("Cannot update playbook configuration %s "
                        "(unique constraint violation)",
                        self.request_json["data"]["name"])
            raise http_exceptions.CannotUpdateModelWithSuchParameters() \
                from exc

        LOG.info("Playbook configuration %s was updated by %s",
                 item_id, self.initiator_id)

        return item

    @auth.AUTH.require_authorization("api", "create_playbook_configuration")
    @validators.require_schema(POST_SCHEMA)
    def post(self):
        cluster_model = self.get_cluster_model(self.request_json["cluster_id"])

        plugs = plugins.get_public_playbook_plugins()
        if self.request_json["playbook_id"] not in plugs:
            raise http_exceptions.UnknownPlaybookError(
                self.request_json["playbook_id"])
        plug = plugs[self.request_json["playbook_id"]]()

        servers_for_playbook = self.get_servers_for_playbook(
            plug,
            self.request_json["playbook_id"],
            self.request_json["server_ids"],
            cluster_model
        )
        try:
            plug.SERVER_LIST_POLICY.check(cluster_model, servers_for_playbook)
        except ValueError as exc:
            raise http_exceptions.ServerListPolicyViolation(
                self.request_json["playbook_id"],
                plug.SERVER_LIST_POLICY,
                exc
            )

        try:
            pcmodel = playbook_configuration.PlaybookConfigurationModel.create(
                name=self.request_json["name"],
                playbook_id=self.request_json["playbook_id"],
                cluster=cluster_model,
                servers=servers_for_playbook,
                initiator_id=self.initiator_id,
                hints=self.request_json["hints"]
            )
        except base_exceptions.UniqueConstraintViolationError as exc:
            LOG.warning(
                "Cannot create cluster %s (unique constraint "
                "violation)",
                self.request_json["name"]
            )
            raise http_exceptions.ImpossibleToCreateSuchModel() from exc
        except base_exceptions.ClusterMustBeDeployedError as exc:
            mid = cluster_model.model_id
            LOG.warning(
                "Attempt to create playbook configuration for not "
                "deployed cluster %s", mid)
            raise http_exceptions.ClusterMustBeDeployedError(mid) from exc

        LOG.info("Playbook configuration %s (%s) created by %s",
                 self.request_json["name"], pcmodel.model_id,
                 self.initiator_id)

        return pcmodel

    @auth.AUTH.require_authorization("api", "delete_playbook_confuiguration")
    @validators.with_model(playbook_configuration.PlaybookConfigurationModel)
    def delete(self, item_id, item):
        try:
            item.delete()
        except base_exceptions.CannotUpdateDeletedModel as exc:
            LOG.warning("Cannot delete deleted role %s", item_id)
            raise http_exceptions.CannotUpdateDeletedModel() from exc

        LOG.info("Playbook configuration %s was deleted by %s",
                 item_id, self.initiator_id)

        return item

    def get_servers_for_playbook(self, plug, playbook_id, suggested_servers,
                                 cluster_model):
        if not plug.REQUIRED_SERVER_LIST:
            return cluster_model.server_list

        if not suggested_servers:
            raise http_exceptions.ServerListIsRequiredForPlaybookError(
                playbook_id
            )

        servers = server.ServerModel.find_by_model_id(*suggested_servers)
        if not isinstance(servers, list):
            servers = [servers]
        if len(servers) != len(set(suggested_servers)):
            raise ValueError(
                "All suggested servers were not found. "
                "Suggested servers were {0}".format(suggested_servers))

        deleted_servers = [srv for srv in servers if srv.time_deleted]
        if deleted_servers:
            raise ValueError(
                "Some servers were deleted: {0}".format(
                    ", ".join(srv.model_id for srv in deleted_servers)))
        return servers

    def get_cluster_model(self, cluster_id):
        cluster_model = cluster.ClusterModel.find_by_model_id(cluster_id)

        if not (cluster_model and not cluster_model.time_deleted):
            raise http_exceptions.UnknownClusterError(cluster_id)

        return cluster_model
