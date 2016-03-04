#!/usr/bin/env python3
# pylint: disable=line-too-long, logging-format-interpolation
"""
Python class for log processing
:todo 1: LZMA support commented out b/c Scripts Python3 has lzma, but missing dependency '_lzma' (?!?!)
"""

import bz2
import gzip
import locale
import os
import re

# import lzma
import random
import logging
from logging.handlers import SysLogHandler

__author__ = 'jantonacci'  # So I wrote a thing
__version__ = '0.1.0'  # Beta!


class Base:
    """
    Python class for log processing - Base
    :todo : Write better docstring
    """

    def __init__(self, level=logging.CRITICAL, regex=None, string=None, file=None) -> None:
        """
        Init an empty Base class unless file list provided
        :param level: minimum event level to log
        :type level: logging.level (logging.DEBUG for verbose, import logging)
        :param regex: regex to match
        :type regex: list (re.compile, import re)
        :param string: strings to match
        :type string: list
        :param file: files to search
        :type file: list
        :rtype: None
        """
        if regex is None:
            regex = []
        if string is None:
            string = []
        if file is None:
            file = []
        self.catalog = {}
        self.logger = Logger(stdout=True, system=False, usage=False, level=level)
        self.logger.debug('Base class init')
        if file:
            self.f_search(regex=regex, string=string, file=file)

    def __call__(self):
        """
        Return Base.catalog dict
        :param: None
        :return: catalog
        :rtype: dict
        """
        self.logger.debug('Base class, method \'__call__\' enter')
        return self.catalog

    def f_search(self, regex=None, string=None, nregex=None, nstring=None, file=None) -> None:
        """
        Populates Base.catalog values from a list of
        files.  Providing a search regex is optional (defaults entire line).
        Providing a list of file path/names is also optional if
        Base.catalog has existing keys.
        NOTE: This is the only method to add Base.catalog.keys - other methods ignore bad keys!
        :param regex: regex to match
        :type regex: list (re.compile, import re)
        :param string: strings to match
        :type string: list
        :param nregex: regex to NOT match
        :type nregex: list (re.compile, import re)
        :param nstring: strings to NOT match
        :type nstring: list
        :param file: files to search
        :type file: list
        :return: None
        :rtype: None
        """
        if string is None:
            string = []
        if regex is None:
            regex = []
        if nstring is None:
            nstring = []
        if nregex is None:
            nregex = []
        if file is None:
            file = self.catalog.keys()
        self.logger.debug('Base class, method \'f_search\' enter')
        for key in file:
            result = []
            with Opener(key) as open_key:
                if open_key and open_key.handle:
                    for line in open_key.handle:
                        if not re.match(r'^\s*$', line):
                            line = line.strip()
                            if regex or string:
                                for item in regex:
                                    if item.search(line):
                                        result.append(line)
                                for item in string:
                                    if item in line:
                                        result.append(line)
                            elif nregex or nstring:
                                for item in regex:
                                    if not item.search(line):
                                        result.append(line)
                                for item in string:
                                    if item not in line:
                                        result.append(line)
                            else:
                                result.append(line)
                else:
                    self.logger.debug('Base class, method \'f_search\' - invalid file \'{k}\''.format(k=key))
            if result:
                self.catalog[key] = sorted(list(set(result)))
        self.logger.debug('Base class, method \'f_search\' exit')

    def c_search(self, regex=None, string=None, nregex=None, nstring=None, file=None):
        """
        Returns lines of text in Base.catalog values.
        Providing a search regex is optional (defaults entire line).
        Providing a list of file path/names is also optional if
        Base.catalog has existing keys. Less time, I/O using catalog!
        - use case - Base.catalog values contain entire file content.
        We want a subset of Base.catalog values, regardless of key.
        :param regex: regex to match
        :type regex: list (re.compile, import re)
        :param string: strings to match
        :type string: list
        :param nregex: regex to NOT match
        :type nregex: list (re.compile, import re)
        :param nstring: strings to NOT match
        :type nstring: list
        :param file: files to search
        :type file: list
        :return: result
        :rtype: dict
        """
        if regex is None:
            regex = []
        if string is None:
            string = []
        if nregex is None:
            nregex = []
        if nstring is None:
            nstring = []
        self.logger.debug('Base class, method \'c_search\' enter')
        if file is not None:
            file = list(key for key in file if key in self.catalog.keys())
        elif file is None:
            file = self.catalog.keys()
        if not file:
            return []
        result = {}
        for key in file:
            if regex or string:
                for line in self.catalog[key]:
                    for item in regex:
                        if item.search(line):
                            if key in result.keys():
                                result[key].append(line)
                            else:
                                result[key] = [line]
                    for item in string:
                        if item in line:
                            if key in result.keys():
                                result[key].append(line)
                            else:
                                result[key] = [line]
            elif nregex or nstring:
                for line in self.catalog[key]:
                    for item in nregex:
                        if not item.search(line):
                            if key in result.keys():
                                result[key].append(line)
                            else:
                                result[key] = [line]
                    for item in nstring:
                        if item not in line:
                            if key in result.keys():
                                result[key].append(line)
                            else:
                                result[key] = [line]
            else:
                result[key] = self.catalog[key]
        self.logger.debug('Base class, method \'c_search\' exit')
        return result

    def c_nsearch(self, regex=None, string=None, file=None):
        """
        Returns lines of text in Base.catalog values.
        Providing a search regex is optional (defaults entire line).
        Providing a list of file path/names is also optional if
        Base.catalog has existing keys. Less time, I/O using catalog!
        - use case - Base.catalog values contain entire file content.
        We want a subset of Base.catalog values, regardless of key.
        :param regex: regex to NOT match, transposed to nregex param
        :type regex: list (re.compile, import re)
        :param string: strings to NOT match, transposed to nstring param
        :type string: list
        :param file: files to search
        :type file: list
        :return: result
        :rtype: dict
        """
        self.c_search(self, nregex=regex, nstring=string, file=file)

    def c_replace(self, regex=None, string=None, nregex=None, nstring=None, file=None):
        """
        Replaces lines of text in Base.catalog values.
        Providing a search regex is optional (defaults entire line).
        Providing a list of file path/names is also optional if
        Base.catalog has existing keys. Less time, I/O using catalog!
        - use case - Base.catalog values contain entire file content.
        We want only lines matching a regex now in Base.catalog values
        :param regex: regex to match
        :type regex: list (re.compile, import re)
        :param string: strings to match
        :type string: list
        :param nregex: regex to NOT match
        :type nregex: list (re.compile, import re)
        :param nstring: strings to NOT match
        :type nstring: list
        :param file: files to search
        :type file: list
        :return: None
        :rtype: None
        """
        if regex is None:
            regex = []
        if string is None:
            string = []
        if nregex is None:
            nregex = []
        if nstring is None:
            nstring = []
        if file is None:
            file = self.catalog.keys()
        self.logger.debug('Base class, method \'c_replace\' enter')
        if file is not None:
            file = list(key for key in file if key in self.catalog.keys())
        elif file is None:
            file = self.catalog.keys()
        if not file:
            return []
        for key in file:
            result = self.__flatten(list(self.c_search(regex=regex,
                                                       string=string,
                                                       nregex=nregex,
                                                       nstring=nstring,
                                                       file=[key]).values()))
            if result:
                self.logger.info('Base class, method \'c_replace\' - insert result in key')
                self.catalog[key] = result
            else:
                self.logger.info('Base class, method \'c_search\' - empty result, delete key')
                del self.catalog[key]
        self.logger.debug('Base class, method \'c_replace\' exit')

    def c_nreplace(self, regex=None, string=None, file=None):
        """
        Replaces lines of text in Base.catalog values NOT matching values.
        Providing a search regex is optional (defaults entire line).
        Providing a list of file path/names is also optional if
        Base.catalog has existing keys. Less time, I/O using catalog!
        - use case - Base.catalog values contain entire file content.
        We want only lines matching a regex now in Base.catalog values
        :param regex: regex to NOT match, transposed to nregex param
        :type regex: list (re.compile, import re)
        :param string: strings to NOT match, transposed to nstring param
        :type string: list
        :param file: files to search
        :type file: list
        :return: None
        :rtype: None
        """
        self.c_replace(self, nregex=regex, nstring=string, file=file)

    def c_keys(self, regex=None, string=None, nregex=None, nstring=None):
        """
        Returns file path/names in Base.catalog keys
        :param regex: regex to match
        :type regex: list (re.compile, import re)
        :param string: strings to match
        :type string: list
        :param nregex: regex to NOT match
        :type nregex: list (re.compile, import re)
        :param nstring: strings to NOT match
        :type nstring: list
        :return: index
        :rtype: list
        """
        if regex is None:
            regex = []
        if string is None:
            string = []
        self.logger.debug('Base class, method \'c_keys\' enter')
        index = []
        if regex or string:
            for key in self.catalog.keys():
                for item in regex:
                    if item.search(key):
                        index.append(key)
                for item in string:
                    if item in key:
                        index.append(key)
        elif nregex or nstring:
            for key in self.catalog.keys():
                for item in regex:
                    if not item.search(key):
                        index.append(key)
                for item in string:
                    if item not in key:
                        index.append(key)
        else:
            for key in self.catalog.keys():
                index.append(key)
        self.logger.debug('Base class, method \'c_keys\' exit')
        if index:
            self.logger.info('Base class, method \'c_keys\' - return result')
            return sorted(list(set(index)))
        else:
            self.logger.info('Base class, method \'c_keys\' - empty result')
            return []

    def c_values(self, regex=None, string=None, nregex=None, nstring=None, file=None):
        """
        Returns lines of text in Base.catalog values.
        Providing a search regex is optional (defaults entire line).
        Providing a list of file path/names is also optional if
        Base.catalog has existing keys. Less time, I/O using catalog!
        - use case - Base.catalog values contain entire file content.
        We want a subset of Base.catalog values, regardless of key.
        :param regex: regex to match
        :type regex: list (re.compile, import re)
        :param string: strings to match
        :type string: list
        :param nregex: regex to NOT match
        :type nregex: list (re.compile, import re)
        :param nstring: strings to NOT match
        :type nstring: list
        :param file: files to search
        :type file: list
        :return: result
        :rtype: list
        """
        if regex is None:
            regex = []
        if string is None:
            string = []
        if file is None:
            file = self.catalog.keys()
        self.logger.debug('Base class, method \'c_values\' enter')
        if file is not None:
            file = list(key for key in file if key in self.catalog.keys())
        elif file is None:
            file = self.catalog.keys()
        if not file:
            return []
        return self.__flatten(list(self.c_search(regex=regex,
                                                 string=string,
                                                 nregex=nregex,
                                                 nstring=nstring,
                                                 file=file).values()))

    def __flatten(self, values):
        """
        Returns lines from a list of lists.
        Private, called by Base.c_values()
        :param values: files to search
        :type values: list
        :return: result
        :rtype: list
        """
        result = []
        for item in values:
            if type(item) is list:
                result.extend(self.__flatten(item))
            else:
                result.append(item)
        return result


class Logger:
    """
    Logging
    """

    def __init__(self, stdout=True, system=False, usage=False, custom=None, level=logging.INFO):
        """
        Basic logging made easy - Logger
        :param stdout: Logging to STDOUT
        :type stdout: bool
        :param system: Logging to syslog on localhost
        :type system: bool
        :param usage: Logging to syslog in default remote host
        :type usage: bool
        :param level: minimum event level to log
        :type level: logging.level (logging.DEBUG for verbose, import logging)
        :param custom: Logging to syslog in custom remote host
        :type custom: dict
        """

        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d PID%(process)d:%(levelname)-8s:%(filename)s:%(funcName)-15s:%(message)s',
            '%Y-%m-%dT%H:%M:%S')

        if custom is None:
            custom = {}

        if stdout:
            # Create STDERR logging destination - incl. for BRB and development
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            # Create a new instance named stdout - separate from root and customize
            self.stdout = logging.getLogger('stdout')
            # Modify stdout to use both syslog and console_handler logging
            self.stdout.addHandler(console_handler)
            # Explicitly set minimum logging level INFO
            self.stdout.setLevel(level)

        if system:
            # Create localhost sylog destination - incl. for system logging
            self.system = self.__custom(udp_port=514, name='system', level=level,
                                        formatter=formatter)

        if usage:
            # Create remote syslog destination - incl. for GS Tools Usage Tracking, vDiag
            self.usage = self.__custom(hostname='usage.gsstools.vmware.com', udp_port=514, name='usage',
                                       level=level, formatter=formatter)

        if 'hostname' in custom.keys():
            try:
                self.custom = self.__custom(**custom)
            except RuntimeWarning:
                pass

    @staticmethod
    def __custom(hostname='localhost', udp_port=514, name=hex(hash(random.random())), level=logging.INFO,
                 formatter=None):
        """
        Create a custom syslog.
        Private, called by Logger.__init__
        :param hostname: IP or DNS name for syslog host
        :type hostname: str
        :param udp_port: syslog listening port - UDP only, no TCP
        :type udp_port: int
        :param name: Unique name for logger
        :type name: str
        :param formatter: Format logging better, default is no bueno
        :type formatter: logging.Formatter
        :param level: minimum event level to log
        :type level: logging.level (logging.DEBUG for verbose, import logging)
        :return: custom
        :rtype: logging.getLogger
        """
        if formatter is None:
            formatter = logging.Formatter(
                '%(asctime)s.%(msecs)03d PID%(process)d:%(levelname)-8s:%(filename)s:%(funcName)-15s:%(message)s',
                '%Y-%m-%dT%H:%M:%S')

        # Create remote sylog destination - incl. for system logging
        custom_handler = SysLogHandler(address=(hostname, udp_port))
        custom_handler.setFormatter(formatter)
        # Create a new instance named custom - separate from root and customize
        custom = logging.getLogger(name)
        # Modify STDOUT to use both syslog and console_handler logging
        custom.addHandler(custom_handler)
        # Explicitly set minimum logging level INFO
        custom.setLevel(level)
        return custom

    def debug(self, message: str = '') -> None:
        """
        Pass DEBUG level message to all existing logging.Logger objects
        :param message: Event to log, default is '' (empty)
        :type message: str
        :return: None
        :rtype: None
        """
        if 'stdout' in self.__dict__.keys():
            self.stdout.debug(message)
        if 'system' in self.__dict__.keys():
            self.stdout.debug(message)
        if 'usage' in self.__dict__.keys():
            self.stdout.debug(message)
        if 'custom' in self.__dict__.keys():
            self.stdout.debug(message)

    def info(self, message: str = '') -> None:
        """
        Pass INFO level message to all existing logging.Logger objects
        :param message: Event to log, default is '' (empty)
        :type message: str
        :return: None
        :rtype: None
        """
        if 'stdout' in self.__dict__.keys():
            self.stdout.info(message)
        if 'system' in self.__dict__.keys():
            self.system.info(message)
        if 'usage' in self.__dict__.keys():
            self.usage.info(message)
        if 'custom' in self.__dict__.keys():
            self.custom.info(message)

    def warning(self, message: str = '') -> None:
        """
        Pass WARNING level message to all existing logging.Logger objects
        :param message: Event to log, default is '' (empty)
        :type message: str
        :return: None
        :rtype: None
        """
        if 'stdout' in self.__dict__.keys():
            self.stdout.warning(message)
        if 'system' in self.__dict__.keys():
            self.system.warning(message)
        if 'usage' in self.__dict__.keys():
            self.usage.warning(message)
        if 'custom' in self.__dict__.keys():
            self.custom.warning(message)

    def error(self, message: str = '') -> None:
        """
        Pass ERROR level message to all existing logging.Logger objects
        :param message: Event to log, default is '' (empty)
        :type message: str
        :return: None
        :rtype: None
        """
        if 'stdout' in self.__dict__.keys():
            self.stdout.error(message)
        if 'system' in self.__dict__.keys():
            self.system.error(message)
        if 'usage' in self.__dict__.keys():
            self.usage.error(message)
        if 'custom' in self.__dict__.keys():
            self.custom.error(message)

    def __call__(self, message: str = '') -> None:
        """
        Pass INFO level message to all existing logging.Logger objects
        :param message: Event to log, default is '' (empty)
        :type message: str
        :return: None
        :rtype: None
        """
        self.info(message)


class Opener:
    """
    Intended as internal only, maybe useful external,
    returns file handle for text or gzip based on file extension
    """
    # Support for compressed single files only, exclude multi-file/directory archives (zip, 7z, tar)
    pat_archive = re.compile(r'\.(lzma|zip|tgz|7z|tar|tar\.(gz|bz2|lzma))$', re.IGNORECASE)  # LZMA exclude

    # pat_archive = re.compile(r'\.(zip|tgz|7z|tar|tar\.(gz|bz2|lzma))$', re.IGNORECASE)        # LZMA support

    def __init__(self, f_name=None):
        self.logger = Logger(stdout=True, system=False, usage=False, level=logging.ERROR, custom={})
        self.logger.debug('Logger class init')
        self.f_name = os.path.abspath(f_name)
        self.handle = []

    def __enter__(self):
        if self.f_name is None:
            self.logger.error('File name cannot be empty.')
        elif self.pat_archive.search(self.f_name):
            self.logger.warning('File \'{f}\' not a supported extension.'.format(f=self.f_name))
        elif not os.access(self.f_name, os.R_OK):
            self.logger.warning('File \'{f}\'cannot be read.'.format(f=self.f_name))
        else:
            f_mode = 'rt'
            f_codec = locale.getpreferredencoding(False)  # Or 'UTF-8'
            f_err = 'surrogateescape'  # Or 'ignore'
            try:
                if self.f_name.endswith('.gz') or self.f_name.endswith('.gzip'):
                    with open(self.f_name, 'rb') as byte_handle:
                        if bytearray.fromhex('1f8b08') in byte_handle.read(3):
                            self.handle = gzip.open(self.f_name, mode=f_mode, encoding=f_codec, errors=f_err)
                elif self.f_name.endswith('.bz') or self.f_name.endswith('.bz2'):
                    with open(self.f_name, 'rb') as byte_handle:
                        if bytearray.fromhex('425a68') in byte_handle.read(3):
                            self.handle = bz2.open(self.f_name, mode=f_mode, encoding=f_codec, errors=f_err)
                # elif self.f_name.endswith('.lzma') or self.f_name.endswith('.lzma'):
                #    with open(self.f_name, 'rb') as byte_handle:
                #        if bytearray.fromhex('5d0000') in byte_handle.read(3):
                #            self.handle = lzma.open(self.f_name, mode=f_mode, encoding=f_codec, errors=f_err)
                else:
                    self.handle = open(self.f_name, mode=f_mode, encoding=f_codec, errors=f_err)
                return self
            except IOError:
                self.logger.error('Exception opening \'{f}\'.'.format(f=self.f_name))
                return self

    # noinspection PyUnusedLocal,PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.handle:
            try:
                self.handle.close()
            except IOError:
                pass


def main():
    """
    Main function
    :param: None
    :type: None
    :return: None
    :rtype: None
    """
    pass


if __name__ == '__main__':
    main()

# EOF
