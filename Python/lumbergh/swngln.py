#!/usr/bin/env python3
# pylint: disable=line-too-long, logging-format-interpolation
"""
Python class for log processing from ESXi vm-support bundles
:todo : Write better docstring
"""

import logging
import os
import re

import lumbergh

__author__ = 'jantonacci'  # So I wrote a thing
__version__ = '0.0.1'  # pre-alpha


class Cluster:
    """
    Python class creates ESXi vm-support bundle for Swingline
    """

    def __init__(self, root: list = ['.']):
        self.catalog = {}
        for item in root:
            item = os.path.abspath(item)
            for path, directory, file in os.walk(item):
                bundle = self.get_bundle(root=path)
                if bundle is not None:
                    self.catalog[path] = bundle
                for subdir in directory:
                    subdir = os.path.join(path, subdir)
                    bundle = self.get_bundle(root=subdir)
                    if bundle is not None:
                        self.catalog[subdir] = bundle
        for key in self.catalog.keys():
            print(key)

    def get_bundle(self, root: str = None):
        subdir = os.path.split(root)[1]
        if subdir.startswith('esx-'):
            bundle = Bundle(root=root)
            if bundle.uname:
                return bundle
            else:
                return None
        else:
            return None

    def result(self, key=None):
        """
        Export Bundle hostname, SCSI device to VMFS filesystem mapping, and storage events from vmkernel.log files
        :return: str, dict, dict
        """
        if key in self.catalog.keys():
            uname, vmfs, vmkernel = self.catalog[key].result()  # uname (str), vmfs (dict), vmkernel (dict)
            if uname:
                return uname, vmfs, vmkernel
            else:
                return None
        else:
            return None


class Bundle:
    """
    Python class creates ESXi vm-support bundle for Swingline
    """

    def __init__(self, root: str = '.'):
        """
        - description - Init an Bundle class and populate
        keys with needed file names, values with list of log events
        :param root: Directory path
        :type root: str
        """
        template_dict = {'uname': ['commands/uname_-a.txt'],
                         'vmfs': ['commands/localcli_storage-vmfs-extent-list.txt'],
                         'vmkernel': ['var/run/log/vmkernel.log',
                                      'var/run/log/vmkernel.1',
                                      'var/run/log/vmkernel.2',
                                      'var/run/log/vmkernel.3',
                                      'var/run/log/vmkernel.4',
                                      'var/run/log/vmkernel.5',
                                      'var/run/log/vmkernel.6',
                                      'var/run/log/vmkernel.7',
                                      'var/run/log/vmkernel.8',
                                      'var/run/log/vmkernel.9',
                                      'var/run/log/vmkernel.1.gz',
                                      'var/run/log/vmkernel.2.gz',
                                      'var/run/log/vmkernel.3.gz',
                                      'var/run/log/vmkernel.4.gz',
                                      'var/run/log/vmkernel.5.gz',
                                      'var/run/log/vmkernel.6.gz',
                                      'var/run/log/vmkernel.7.gz',
                                      'var/run/log/vmkernel.8.gz',
                                      'var/run/log/vmkernel.9.gz']}
        self.uname = ''
        self.vmfs = {}
        self.vmkernel = {}
        self.root = os.path.abspath(root)
        self.logger = lumbergh.Logger(stdout=True, system=False, usage=False, level=logging.DEBUG)

        for key in template_dict.keys():
            new_value = []
            for value in template_dict[key]:
                new_value.append(os.path.join(self.root, value))
            template_dict[key] = new_value

        base_uname = lumbergh.Base(string=['VMkernel'], file=template_dict['uname'])
        self.uname = re.sub(r'VMkernel | .*$', '', base_uname.c_values()[0]).lower()
        del base_uname

        base_vmfs = lumbergh.Base()
        base_vmfs.f_search(nregex=[re.compile(r'^(Volume Name.*|__*)$')], file=template_dict['vmfs'])
        for line in base_vmfs.c_values():
            extent = re.sub(r'^.*  *[0-9,a-f]*-[0-9,a-f]*-[0-9,a-f]*-[0-9,a-f]*  *[0-9]  *|  *[0-9] *$', '', line)
            datastore = re.sub(r' *[0-9,a-f]*-[0-9,a-f]*-[0-9,a-f]*-[0-9,a-f]* .*$', '', line)
            if extent and datastore:
                self.vmfs[extent] = datastore
        del base_vmfs

        pat_sdio = re.compile(r'(ScsiDeviceIO.*(Restricting cmd|failed))')
        base_vmkernel = lumbergh.Base(regex=[pat_sdio], string=[' performance has '], file=template_dict['vmkernel'])
        pat_ignore = re.compile(r' 0x(1a|4d,85), ')
        base_vmkernel.c_replace(nregex=[pat_ignore])
        self.vmkernel = base_vmkernel.catalog.copy()
        del base_vmkernel

        del template_dict

    def result(self):
        """
        Export Bundle hostname, SCSI device to VMFS filesystem mapping, and storage events from vmkernel.log files
        :return: str, dict, dict
        """
        return self.uname, self.vmfs, self.vmkernel

# EOF
