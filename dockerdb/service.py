import os
import time
import sys
import shutil
import tempfile
import weakref
import atexit
import functools
import select
import socket

import docker

import dockerdb


start_time = int(time.time())
counter = 0
client = dockerdb.docker_client


def _remove_weakref(service):
    # dereferece weakref
    service = service()
    if service is not None:
        service.remove()


class Service(object):
    """Base class for docker based services"""
    timeout = 30.0
    name = 'service'

    def __init__(self, image, wait=False, **kwargs):
        global counter

        self.client = client

        kwargs.setdefault('detach', True)
        name = 'tmp_{}_{}_{}'.format(start_time, self.name, counter)
        kwargs.setdefault('name', name)
        kwargs.setdefault('network', dockerdb.my_network_id)
        counter += 1

        kwargs.setdefault('volumes', {})
        self.share = tempfile.mkdtemp(name)
        kwargs['volumes'][self.share] = {'bind': self.share, 'mode': 'rw'}

        atexit_callback = functools.partial(_remove_weakref, weakref.ref(self))
        atexit.register(atexit_callback)
        self.container = client.containers.run(image, **kwargs)
        if wait:
            self.wait()

    def inspect(self):
        """get docker inspect data for container"""
        return self.client.api.inspect_container(self.container.id)

    def exec_run(self, command, input_file):
        """Execute a command and pipe data into it """
        exec_info = self.client.api.exec_create(
            self.container.name, command, stdin=True)

        exec_id = exec_info['Id']

        sock = self.client.api.exec_start(exec_id, socket=True)

        if hasattr(sock, "_sock"):
            # On python 3 docker-py returns a socket.SocketIO
            # Wrapper doesn't give access to all needed methods
            # So we extract the low level socket instance
            sock = sock._sock

        sock.setblocking(False)
        output = b''

        while True:
            r_list, w_list, _ = select.select([sock], [sock], [])

            if w_list:
                file_data = input_file.read(4096)

                if file_data == b'':
                    break
                else:
                    sock.send(file_data)

            if r_list:
                socket_output = sock.recv(4096)
                if socket_output == b'':
                    break
                else:
                    output += socket_output

        # TODO Find a way to avoid hardcoded sleep limits for python 2
        # TODO Solutions is still unknown, see: STUD-583
        python_version = sys.version_info[0]
        if python_version < 3:
            time.sleep(1)

        sock.shutdown(socket.SHUT_WR)

        if python_version < 3:
            time.sleep(0.2)

        sock.setblocking(True)
        output += sock.recv(4096 * 100)
        sock.close()

        while True:
            exec_info = self.client.api.exec_inspect(exec_id)
            exit_code = exec_info['ExitCode']
            if exit_code is not None:
                break

        return exit_code, output

    def ip_address(self):
        network_settings = self.inspect()['NetworkSettings']
        ip_address = network_settings['IPAddress']
        if ip_address == '':
            networks = network_settings['Networks']
            assert len(networks) == 1
            network = next(iter(networks.values()))
            ip_address = network['IPAddress']

        return ip_address

    def wait(self, timeout=None):
        if timeout is None:
            timeout = self.timeout

        start = time.time()
        while not self.check_ready() and time.time() - start < timeout:
            time.sleep(0.1)

    def remove(self):
        # this must be safe to call during interpreter shutdown
        # object might already disintegrate
        if hasattr(self, 'container'):
            try:
                self.container.remove(force=True, v=True)
            except docker.errors.NotFound:
                pass

        if os.path.exists(self.share):
            shutil.rmtree(self.share)

    def __del__(self):
        try:
            self.remove()
        except:
            # on interpreter shutdown deleting container will
            # fail as the docker client is already breaking apart.
            # the atexit callback will be called earlier, taking
            # care of this case
            pass


class HTTPServer(Service):
    protocol = 'http'
    port = '80'

    def check_ready(self):
        import requests

        ip = self.ip_address()
        url = '{}://{}:{}'.format(self.protocol, ip, self.port)

        try:
            requests.get(url)
            return True
        except requests.exceptions.ConnectionError:
            return False
