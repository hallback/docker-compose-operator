"""DockerComposeManager Class"""

import subprocess
import sys
import time
import socket

from python_on_whales import docker, DockerClient
from python_on_whales.exceptions import DockerException
from jinja2 import Template

DOCKER_PKGS_IO = ['docker.io', 'docker-compose', 'docker-compose-v2']

class DockerComposeManager:
    """
    Mangages the Docker and containers, such as installing, configuring, etc.
    This class should work independently from juju, such as that it can
    be tested without lauching a full juju environment.
    """

    def install_docker(self):
        """
        Install packages. Juju has already run apt-get upgrade.

        Docs for CE-install: https://docs.docker.com/engine/install/ubuntu/
        """
        try:
            cmd = ['apt-get', 'update']
            subprocess.run(cmd, check = True)
            cmd = ['apt-get', 'install', '-y']
            cmd.extend(DOCKER_PKGS_IO)
            subprocess.run(cmd, check = True)
        except Exception as e:
            # Throw an error to ensure automatic retry later
            print("Error installing Docker", str(e))
            sys.exit(1)

    def get_status(self):
        # TODO: Check if config file is newer than running
        # container.created has time, we can get it by: https://gabrieldemarmiesse.github.io/python-on-whales/sub-commands/compose/#python_on_whales.components.compose.cli_wrapper.ComposeCLI.ps
        # we can also check the config filename here!
        # But we should maybe return a tuple here, not just a string
        # only in charm.py we can set the charm status!
        now = time.strftime("%H:%M:%S")

        # 1 check if docker compose is installed and working
        # 2 check if configuration is written (this function needs "composepath"
        # 3 check if all containers are running
        # 4 show some nice output
        # docker.ps() returns a list of whalescontainers, here the attributes:
        # https://gabrieldemarmiesse.github.io/python-on-whales/objects/containers/#attributes
        containerlist = docker.ps()
        containerstring = list(container.name for container in containerlist)
        status = f"Running {containerstring} ({now})"
        return status

    def docker_compose(self, composepath):
        # TODO: We can also check e.stderr and e.stdout. Maybe add to a logfile?
        # p = Path("/var/log/xxx.log")
        # with p.open(mode="w+") as f:
        #   p.write_text("dkjkf")
        try:
            docker = DockerClient(compose_files=[composepath])
            docker.compose.up(detach=True)
        except DockerException as e:
            return f"Exit code {e.return_code} while running {e.docker_command}"
        return ""

    def render_compose_yaml(self, yaml):
        tmpl = Template(yaml)
        return tmpl.render(hostname = socket.gethostname(),
                           fqdn = socket.getfqdn())
