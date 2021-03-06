.. _decapod_playbook_plugins:

================
Playbook plugins
================

Decapod performs Ceph management through plugins. These plugins support
different tasks, such as cluster deployment, adding and removing of OSDs, and
so on.
This section describes the available playbook plugins and the main options
these plugins support.

The section contains the following topics:

.. toctree::
   :maxdepth: 1

   playbook-plugins/plugin-deploy-ceph-cluster.rst
   playbook-plugins/plugin-upgrade-ceph-cluster.rst
   playbook-plugins/plugin-add-osd.rst
   playbook-plugins/plugin-remove-osd.rst
   playbook-plugins/plugin-add-monitor.rst
   playbook-plugins/plugin-remove-monitor.rst
   playbook-plugins/plugin-add-rgw.rst
   playbook-plugins/plugin-remove-rgw.rst
   playbook-plugins/plugin-add-restapi.rst
   playbook-plugins/plugin-remove-restapi.rst
   playbook-plugins/plugin-purge-cluster.rst
   playbook-plugins/plugin-add-nfs.rst
   playbook-plugins/plugin-telegraf-integration.rst
   playbook-plugins/plugin-purge-telegraf.rst
   playbook-plugins/plugin-cinder-integration.rst
   playbook-plugins/plugin-update-ceph-configuration.rst
   playbook-plugins/plugin-restart-services.rst
