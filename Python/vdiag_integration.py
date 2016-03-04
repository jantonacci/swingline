#!python
#pylint: disable=line-too-long, logging-format-interpolation
"""
- description - vDiag integration library for python
:todo : Write better docstring
"""

import logging
import os
import shutil
from logging import StreamHandler
from logging.handlers import SysLogHandler, SocketHandler

__author__ = 'jantonacci'   # So I wrote a thing
__version__ = '0.0.1'       # pre-alpha

MSG_STATUS = r'"{script}" ver={ver}, ssh="{ssh}", user={user}, cwd="{cwd}"'.format(script=__file__,
                                                                                   ver=__version__,
                                                                                   user=os.getenv('USER'),
                                                                                   cwd=os.getcwd(),
                                                                                   ssh=os.getenv('SSH_CONNECTION'))
MSG_DEFAULT = r'no message or event description'
FMT_DEFAULT = logging.Formatter('%(asctime)s.%(msecs)03d PID%(process)d: %(levelname)-8s: %(filename)s: %(funcName)-15s: %(message)s',
                                '%Y-%m-%dT%H:%M:%S')

class syslogger:
    """
    - description - class for vDiag logging object
    :todo : Write better docstring
    """

    config = {'debug': ''}
    log = logging.getLogger('USAGE_log')
    log.setLevel(logging.INFO)
    syslog_addr_default = 'vdiag-li.eng.vmware.com'
    syslog_port_default = 514
    syslog_proto_default = 'udp'

    # SysLogHandler is UDP only, no TCP protocol option.
    # Includes SocketHandler for TCP protocol option.
    # TODO: SSL/TLS support (?)
    def __init__(self, syslog_addr=syslog_addr_default, syslog_port=syslog_port_default, syslog_proto=syslog_proto_default):
        self.config['syslog_addr'] = syslog_addr
        self.config['syslog_port'] = syslog_port
        self.config['syslog_proto'] = syslog_proto
        if syslog_proto.lower() == 'tcp':
            # Proto specified is 'tcp' - set 'tcp' and use SocketHandler
            self.config['syslog_proto'] = 'tcp'
            self.usage = SocketHandler(self.config['syslog_addr'], self.config['syslog_port'])
        else:
            # Proto specified is not 'tcp' - default to 'udp' and use SysLogHandler
            self.config['syslog_proto'] = 'udp'
            self.usage = SysLogHandler(address=(self.config['syslog_addr'], self.config['syslog_port']))

        self.usage.setFormatter(FMT_DEFAULT)
        self.log.addHandler(self.usage)

    def console(self):
        ## Create STDERR logging destination - incl. for BRB and development
        self.console = StreamHandler()
        self.console.setFormatter(FMT_DEFAULT)
        self.log.addHandler(self.console)

    def msg(self, message=MSG_DEFAULT):
        self.msg_info(message)

    def msg_debug(self, message=MSG_DEFAULT):
        self.log.debug(message)
        if self.config['debug']:
            print message

    def msg_error(self, message=MSG_DEFAULT):
        self.log.error(message)
        if self.config['debug']:
            print message

    def msg_info(self, message=MSG_DEFAULT):
        self.log.info(message)
        if self.config['debug']:
            print message

    def msg_warning(self, message=MSG_DEFAULT):
        self.log.warning(message)
        if self.config['debug']:
            print message

    def debug(self):
        self.config['debug'] = True
        self.log.setLevel(logging.DEBUG)

    def udebug(self):
        self.config['debug'] = False
        self.log.setLevel(logging.INFO)

LOG = syslogger()

def debug():
    LOG.debug()

def udebug():
    LOG.udebug()

def log_status(msg=MSG_DEFAULT):
    if 'start' == msg.lower():
        LOG.msg('start - {msg}'.format(msg=MSG_STATUS))
    elif 'stop' == msg.lower():
        LOG.msg('stop  - {msg}'.format(msg=MSG_STATUS))
    else:
        LOG.msg(msg)

def copy_payload(file_list=['payload_file.ext']):
    err_code = copy_appfile('VDIAG_REPORTS_DIR', file_list)
    return err_code

def copy_applog(file_list=['applog_file.ext']):
    err_code = copy_appfile('VDIAG_LOGDIR', file_list)
    return err_code

def copy_appfile(vdiag_env_var='VDIAG_APPPATH', file_list=['app_file.ext']):
    err_code = 0
    if os.environ.get(vdiag_env_var):
        vdiag_reports_dir = os.path.abspath(os.environ[vdiag_env_var])
        if os.path.exists(vdiag_reports_dir):
            for file_name in file_list:
                file_src = os.path.abspath(file_name)
                if os.path.exists(file_src):
                    file_dst = os.path.join(vdiag_reports_dir, os.path.basename(file_src))
                    try:
                        shutil.move(file_src, file_dst)
                    except RuntimeError:
                        LOG.msg('Failed moving "{s}" to "{d}" - return error code +10'.format(s=file_src, d=file_dst))
                        err_code += 100
                        pass
                else:
                    LOG.msg('Source file does not exist "{s}" - return error code +10'.format(s=file_src))
                    err_code += 10
                    pass
            return err_code
        else:
            LOG.msg('Env var "{v}" has invalid path "{p}" - return error code 1'.format(v=vdiag_env_var,
                                                                                        p=vdiag_reports_dir))
            return 1
    else:
        LOG.msg('Env var "{v}" not defined - return error code 0'.format(v=vdiag_env_var))
        return 1

#EOF
