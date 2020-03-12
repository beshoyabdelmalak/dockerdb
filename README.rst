========
dockerdb
========


.. image:: https://img.shields.io/pypi/v/dockerdb.svg
        :target: https://pypi.python.org/pypi/dockerdb

.. image:: https://readthedocs.org/projects/dockerdb/badge/?version=latest
        :target: https://dockerdb.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://pyup.io/repos/github/FlorianLudwig/dockerdb/shield.svg
     :target: https://pyup.io/repos/github/FlorianLudwig/dockerdb/
     :alt: Updates


Running databases inside temporary docker for testing purposes.

* Free software: Apache Software License 2.0


Status
------

Proof of concept.


Features
--------

* starts temporary mongo containers

* py.test integration
* executes every test against multiple versions of mongo
* resets the temporary mongo container before every test
* restores archived mongo dumps before every test
* support for single member replica sets
* ...


Usage
-----

Dockerdb uses `mongorestore --archive` to restore mongo dumps.
To create an archived dump, run `mongodump --archive > ./dump`
