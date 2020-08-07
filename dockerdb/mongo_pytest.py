from __future__ import absolute_import
import os
import shutil
import subprocess
import logging

import pytest
import dockerdb.mongo


CONTAINER_CACHE = {}

LOG = logging.getLogger(__name__)


def insert_data(client, data):
    for db in data:
        for collection in data[db]:
            entries = data[db][collection]
            re = client[db][collection].insert_many(entries)


def mongorestore(service, restore):
    command = ['mongorestore', "--archive"]

    with open(restore, 'rb') as restore_file:
        exit_code, output = service.exec_run(command, restore_file)

    if exit_code != 0:
        if isinstance(output, bytes):
            output = output.decode('utf-8', errors='ignore')

        LOG.error(output)

        raise subprocess.CalledProcessError(exit_code, command, output)


def get_service(version):
    service = CONTAINER_CACHE[version]
    service.wait()
    service.factory_reset()
    return service


def ensure_service(version, replicaset, port, client_args):
    if version not in CONTAINER_CACHE:
        CONTAINER_CACHE[version] = dockerdb.mongo.Mongo(
            version, wait=False, replicaset=replicaset, exposed_port=port,
            client_args=client_args)


def mongo_fixture(scope='function', versions=['latest'], data=None,
                  restore=None, reuse=True, replicaset=None, port=27017,
                  client_args=None):
    """create ficture for py.test

    Attributes:
        scope (str): py.test scope for this fixture
        versions (list): mongodb versions that should be tested
        data (dict): A dict containing data to be inserted into the database
            before the test.  The structure must be:
            {'db': {
                'collection': [
                    {'document_data': True},
                    {'another': 'document'},
                    ...
                ]
            }}

        restore (str): path to directory containing a mongo dump
        reuse (bool): wether to reuse containers or create a new container
            for every requested injection
        client_args(dict): arguments that get passed to the pymongo client

    """

    # parallelized start of different versions
    if reuse:
        for version in versions:
            ensure_service(version, replicaset, port, client_args)

    @pytest.fixture(scope=scope,  params=versions)
    def mongo(request):
        if reuse:
            service = get_service(request.param)
        else:
            service = dockerdb.service.Mongo(request.param, wait=True,
                                             replicaset=replicaset,
                                             exposed_port=port,
                                             client_args=client_args)

        client = service.pymongo_client()
        service.wait()

        if data:
            insert_data(client, data)

        if restore:
            for i in range(3):
                try:
                    mongorestore(service, restore)
                    break
                except Exception as error:
                    if i == 2:
                        LOG.error('Error while restoring {}'.format(error))
                        raise error
                    else:
                        LOG.warn('Retrying to restore...')

        yield service

        if not reuse:
            service.remove()

    return mongo
