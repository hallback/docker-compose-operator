#!/usr/bin/env python3
# Copyright 2024 Johan Hallbäck
# See LICENSE file for licensing details.

"""Charm the application."""

import logging

# https://ops.readthedocs.io/en/latest
import ops
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus, MaintenanceStatus
from ops import ModelError

# https://docs.python.org/3/library/pathlib.html
from pathlib import Path

from docker_compose_manager import DockerComposeManager

logger = logging.getLogger(__name__)


class DockerComposeCharm(ops.CharmBase):
    """Charm the application."""

    _stored = ops.StoredState()

#    def __init__(self, *args):
    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        #super().__init__(*args)
        self.docker_compose_manager = DockerComposeManager()

        # https://discourse.charmhub.io/t/a-charms-life/5938
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)
        # Actions:
        self.framework.observe(self.on.recompose_action, self._recompose_action)
        # it is also possible to observe status:
        # https://ops.readthedocs.io/en/latest/reference/ops.html#ops.CollectStatusEvent
        # https://discourse.charmhub.io/t/how-to-set-a-charms-status/11771
        # we can add statuses and have them evaluated after every hook run!
        # is triggered on leader unit!
        # note distinction between applications and units
        # will be run after *every* hook, not just update-status!
        #self.framework.observe(self.collect_app_status, self._collect_app_status)
        #self.framework.observe(self.on.collect_unit_status, self._on_collect_unit_status)
        #
        # BUT WE WILL NEED TO MOVE ALL CHECKS TO THE COLLECT STATUS FUNCTIONS
        #
        # My ideas: Blocked is for Juju things that haven't happened yet:
        # - you need to supply more configuration
        # - there are missing relations you need to add
        # - Maybe there's something you could correct by running an action
        # For things that didn't work, throw an error!
        # - it will be retried automatically

        # https://ops.readthedocs.io/en/latest/explanation/storedstate-uses-limitations.html
        # Summary: Track changes by states of files or commands, not through
        # stored state whenever possible.
        self._stored.set_default(docker_source=set())
        self._stored.set_default(docker_root=set())

    #def _on_collect_unit_status(self, event: ops.CollectStatusEvent):
    #    status = self.docker_compose_manager.get_status()
    #    event.add_status(ActiveStatus(status))
    #    logger.info(status)

    def recompose(self):
        # TODO (minor): This will go through with a warning if
        # docker_compose_yml never was set
        composepath = f"{self.config['docker_root']}/docker-compose.yml"
        err = self.docker_compose_manager.docker_compose(composepath)
        if err:
            self.unit.status = BlockedStatus("docker compose failed, examine and run recompose action")
        self.unit.status = ActiveStatus(f"start: {self.docker_compose_manager.get_status()}")
        self.open_ports()

    def open_ports(self):
        portset = self.docker_compose_manager.get_portset()
        logger.info(portset)
        portlist = list()
        for p in portset:
            portsplit = p.split('/')
            portlist.append(ops.Port(port=portsplit[0], protocol=portsplit[1]))
        print(portlist)
        self.unit.set_ports(*portlist)

    def _recompose_action(self, event):
        self.recompose()
 
    def _on_install(self, event):
        self.unit.status = MaintenanceStatus("Docker packages are now being installed")
        logger.info("Docker packages are now being installed")
        self.docker_compose_manager.install_docker()
        self.unit.status = ActiveStatus("Installed Docker packages")

    def _on_start(self, event: ops.StartEvent):
        """We do compose on every start to prevent config drift"""
        self.recompose()
        version = self.docker_compose_manager.get_version()
        if version is not None:
            self.unit.set_workload_version(version)

    # TODO: We should maybe have a configuration for the log file
    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        # Maybe we shouldn't be allowed to change this?
        if self.config['docker_root'] != self._stored.docker_root:
            logger.info(f"config-changed: Detected change on docker_root, stored: "
            f"{self._stored.docker_root}, new: {self.config['docker_root']}")
            self._stored.docker_root = self.config["docker_root"]
            p = Path(self.config['docker_root'])
            p.mkdir(mode=0o755, parents=True, exist_ok=True)
        else:
            logger.info(f"config-changed: docker_root not changed")

        if not self.config.get('docker_compose_yml'):
            self.unit.status = BlockedStatus("docker_compose_yml is not set")
            return

        # TODO: compare file contents with config instead? could always be done.
        # Good for yaml? https://github.com/yaml/pyyaml (python3-yaml)
        composepath = f"{self.config['docker_root']}/docker-compose.yml"
        dcyml = Path(composepath)
        ondisk = dcyml.read_text() if dcyml.exists() else ""
        newcfg = self.docker_compose_manager.render_compose_yaml(self.config.get('docker_compose_yml'))
        if newcfg != ondisk:
            logger.info("config-changed: config is now changing on disk")
            dcyml.write_text(newcfg)
            # The file has changed, we must run compose through a Juju action
            self.unit.status = MaintenanceStatus("docker_compose_yml changed, run recompose action")

    def _on_update_status(self, event):
        status = self.docker_compose_manager.get_status()
        self.unit.status = ActiveStatus(status)
        logger.info(status)


if __name__ == "__main__":  # pragma: nocover
    ops.main(DockerComposeCharm)  # type: ignore
