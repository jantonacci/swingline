#!/usr/bin/env python
# pylint: disable=line-too-long
""" Swingline:  investigating ESXi entire cluster's block storage events using
Microsoft Excel spreadsheets with preconfigured autofilters and heatmaps """
import argparse
import gzip
import logging
import os
import re
import shutil
import sys
import time
from logging.handlers import SysLogHandler

import dataset
import xlsxwriter

## GLOBAL

__version__ = "0.0.74"

## Setup database instance from module dataset
## Create a new database in memory - sqllite is inlcuded in dataset
DB = dataset.connect('sqlite:///:memory:')
## Create a new database tables for storage latency and io command failures
TBL_STORAGE = DB.get_table('storage')

## Create a new instance named USAGE_TRACKING - separate from root and customize
USAGE_TRACKING = logging.getLogger('USAGE_TRACKING')

## Create a new instance named RUNTIME_LOG - separate from root and customize
RUNTIME_LOG = logging.getLogger('RUNTIME_LOG')

## Setup logging to flexibly handle script progress notices and exceptions from
## module logging.  Create logging message and date format instance for common
## use ammong multiple logging destinations.
FMT_LOG_DEFAULT = logging.Formatter(
    '%(asctime)s.%(msecs)03d PID%(process)d:%(levelname)-8s:%(filename)s:%(funcName)-15s:%(message)s',
    '%Y-%m-%dT%H:%M:%S')

## Create remote sylog destination - incl. for system logging
LOCALHOST = SysLogHandler(address=('localhost', 514))
LOCALHOST.setFormatter(FMT_LOG_DEFAULT)

## Create STDERR logging destination - incl. for BRB and development
CONSOLE = logging.StreamHandler()
CONSOLE.setFormatter(FMT_LOG_DEFAULT)


## function main
def main():
    """ MAIN function """

    set_usage_tracking()
    set_runtime_log()
    opt_dict = parse_opt()

    # Log how Swingline was called for usage metrics
    track_use('start')

    ## Create four database entries (one per category) from 1970-01-01 with KBs
    insert_sample()

    ## Call function pop_db - populates database
    pop_db(opt_dict['srdata'])

    ## Call function check_db for results compare
    ##  ex. log review shows 20 events and db contains four samples
    check_db()

    ## Create a dictionary of standard SQL queries
    cat_dict = dict(storage='date,time,category,host,fname,dev,dsname,latency,lavg,world,cmd,t10,sense,asense,raw',
                    latency='date,time,host,fname,dev,dsname,world,latency,lavg,raw',
                    iofails='date,time,host,fname,dev,dsname,world,cmd,t10,sense,raw',
                    sioclmt='date,time,host,fname,dev,dsname,world,cmd,t10,raw',
                    apdpdls='date,time,host,fname,dev,dsname,raw',
                    order='date,time,host')

    sql_dict = dict(storage='SELECT DISTINCT {fields} FROM {table} ORDER BY {order}'.format(table='storage',
                                                                                            fields=cat_dict['storage'],
                                                                                            order=cat_dict['order']),
                    latency='SELECT DISTINCT {fields} FROM {table} WHERE category=\'{cat}\' ORDER BY {order}'.format(
                        table='storage', fields=cat_dict['latency'], cat='latency', order=cat_dict['order']),
                    iofails='SELECT DISTINCT {fields} FROM {table} WHERE category=\'{cat}\' ORDER BY {order}'.format(
                        table='storage', fields=cat_dict['iofails'], cat='iofails', order=cat_dict['order']),
                    sioclmt='SELECT DISTINCT {fields} FROM {table} WHERE category=\'{cat}\' ORDER BY {order}'.format(
                        table='storage', fields=cat_dict['sioclmt'], cat='sioclmt', order=cat_dict['order']),
                    apdpdls='SELECT DISTINCT {fields} FROM {table} WHERE category=\'{cat}\' ORDER BY {order}'.format(
                        table='storage', fields=cat_dict['apdpdls'], cat='apdpdls', order=cat_dict['order']))

    ## Generate results formats specified from command line options
    if opt_dict['csv_bool']:
        ## Call function freeze_tbl from module swingline to generate CSV
        freeze_tbl({'format': 'csv', 'freeze_file': opt_dict['csv_file'], 'sql_query': sql_dict['storage']})
    if opt_dict['json_bool']:
        ## Call function freeze_tbl from module swingline to generate JSON
        freeze_tbl({'format': 'json', 'freeze_file': opt_dict['json_file'], 'sql_query': sql_dict['storage']})
    if opt_dict['summary_bool']:
        ## Call function to generate Top Ten Summary - before XLSX
        freeze_summary({'opt_dict': opt_dict, 'sql_dict': sql_dict})
    if opt_dict['xlsx_bool']:
        ## Call function opt_dict['xlsx'] to generate XLSX - after Summary
        freeze_xlsx({'opt_dict': opt_dict, 'sql_query': sql_dict['storage']})

    milton_waddams()
    track_use('stop')
    sys.exit(0)


def set_usage_tracking():
    """ SET USAGE TRACKING function """
    ## Create remote syslog destination - incl. for GS Tools Usage Tracking, vDiag
    vrli_usage = SysLogHandler(address=('usage.gsstools.vmware.com', 514))
    vrli_usage.setFormatter(FMT_LOG_DEFAULT)

    ## Modify RUNTIME_LOG to use both syslog and CONSOLE logging
    USAGE_TRACKING.addHandler(vrli_usage)
    ## Explicitly set minimum logging level INFO
    USAGE_TRACKING.setLevel(logging.INFO)


def set_runtime_log():
    """ SET RUNTIME LOG function """
    ## Modify RUNTIME_LOG to use both syslog and CONSOLE logging
    RUNTIME_LOG.addHandler(LOCALHOST)
    RUNTIME_LOG.addHandler(CONSOLE)
    ## Explicitly set minimum logging level INFO
    RUNTIME_LOG.setLevel(logging.INFO)


def set_opt_default():
    """ SET OPT DEFAULT function """
    ## Setup command line options defaults
    opt_dict = {'tstamp': time.strftime("-%Y%m%d-%H%M%S"),
                'srdata': os.path.abspath('.'),
                'rpt_dir': os.path.abspath('.'),
                'tmp_dir': os.path.abspath(os.getenv('HOME')),
                'csv_bool': False,
                'json_bool': False,
                'xlsx_bool': True,
                'summary_bool': True}

    opt_dict.update(
        {'csv_file': '{dirpath}/swingline{unique}.csv'.format(dirpath=opt_dict['srdata'], unique=opt_dict['tstamp']),
         'json_file': '{dirpath}/swingline{unique}.json'.format(dirpath=opt_dict['srdata'], unique=opt_dict['tstamp']),
         'xlsx_file': '{dirpath}/swingline{unique}.xlsx'.format(dirpath=opt_dict['srdata'], unique=opt_dict['tstamp']),
         'summary_file': '{dirpath}/swingline{unique}.txt'.format(dirpath=opt_dict['srdata'],
                                                                  unique=opt_dict['tstamp'])})

    return opt_dict


def set_parser(opt_dict):
    """ SET PARSER function """
    parser = argparse.ArgumentParser(prog=os.path.basename(__file__),
                                     description='''Swingline''',
                                     epilog='''See https://wiki.eng.vmware.com/GSS/Tool/swingline''')
    parser.add_argument('-e', '--export',
                        nargs='?',
                        default='default',
                        const='default',
                        choices=['all', 'default', 'none', 'csv', 'json', 'xlsx', 'summary'],
                        action='store',
                        dest='export',
                        help=': export report(s) in specified format - default is XLSX and Summary')
    parser.add_argument('-b', '--bundle_dir',
                        nargs='?',
                        default='default',
                        const='default',
                        action='store',
                        dest='bundle_dir',
                        help=': vm-support bundle extracted directory - default is "{dir}"'.format(
                            dir=opt_dict['srdata']))
    parser.add_argument('-r', '--rpt_dir',
                        nargs='?',
                        default='default',
                        const='default',
                        action='store',
                        dest='rpt_dir',
                        help=': export report(s) in directory - default is "{dir}"'.format(dir=opt_dict['rpt_dir']))
    parser.add_argument('-t', '--tmp_dir',
                        nargs='?',
                        default='default',
                        const='default',
                        action='store',
                        dest='tmp_dir',
                        help=': create temporary file(s) in directory - default is "{dir}"'.format(
                            dir=opt_dict['tmp_dir']))
    parser.add_argument('-l', '--log_dir',
                        nargs='?',
                        default='default',
                        const='default',
                        action='store',
                        dest='log_dir',
                        help=': log to file in directory - default is console')
    parser.add_argument('-v', '--debug',
                        action='store_true',
                        dest='debug',
                        help=': console logging level debug')
    parser.add_argument('-s', '--silent',
                        action='store_true',
                        dest='silent',
                        help=': console logging level is none')
    parser.add_argument('-q', '--quiet',
                        action='store_true',
                        dest='quiet',
                        help=': console logging level is warning and higher')
    parser.add_argument('--version',
                        action='version',
                        version='%(prog)s {ver}'.format(ver=__version__),
                        help=': version information')
    return parser


def parse_opt_export(arg_dict, opt_dict):
    """ PARSE OPT EXPORT function """
    if arg_dict.export and not 'default' in arg_dict.export:
        if 'all' in arg_dict.export.lower():
            ## Generate ALL formats
            opt_dict.update({'summary_bool': True,
                             'csv_bool': True,
                             'json_bool': True,
                             'xlsx_bool': True})
        elif 'none' in arg_dict.export.lower():
            ## Generate ALL formats
            opt_dict.update({'summary_bool': False,
                             'csv_bool': False,
                             'json_bool': False,
                             'xlsx_bool': False})
        elif 'csv' in arg_dict.export.lower():
            ## Generate ALL formats
            opt_dict.update({'summary_bool': False,
                             'csv_bool': True,
                             'json_bool': False,
                             'xlsx_bool': False})
        elif 'json' in arg_dict.export.lower():
            ## Generate ALL formats
            opt_dict.update({'summary_bool': False,
                             'csv_bool': False,
                             'json_bool': True,
                             'xlsx_bool': False})
        elif 'xlsx' in arg_dict.export.lower():
            ## Generate ALL formats
            opt_dict.update({'summary_bool': False,
                             'csv_bool': False,
                             'json_bool': False,
                             'xlsx_bool': True})
        else:
            RUNTIME_LOG.warning(
                'Invalid arg_dict.export arguement "{arg}" - using default'.format(arg=arg_dict.export.lower()))

    return opt_dict


def parse_opt():
    """ PARSE OPT funtion """
    opt_dict = set_opt_default()
    parser = set_parser(opt_dict)
    arg_dict = parser.parse_args()

    opt_dict = parse_opt_bundle(arg_dict, opt_dict)
    opt_dict = parse_opt_temp(arg_dict, opt_dict)
    opt_dict = parse_opt_export(arg_dict, opt_dict)
    opt_dict = parse_opt_logging(arg_dict, opt_dict)

    return opt_dict


def parse_opt_bundle(arg_dict, opt_dict):
    """ PARSE OPT BUNDLE function """
    if arg_dict.bundle_dir and not 'default' in arg_dict.bundle_dir:
        if os.path.exists(arg_dict.bundle_dir):
            opt_dict['srdata'] = os.path.abspath(arg_dict.bundle_dir)
        else:
            RUNTIME_LOG.error(
                'Invalid vm-support bundle extracted directory arguement "{arg}"'.format(arg=arg_dict.bundle_dir))
            sys.exit(1)

    if arg_dict.rpt_dir and not 'default' in arg_dict.rpt_dir:
        if os.path.exists(arg_dict.rpt_dir):
            opt_dict.update({'csv_file': '{dirpath}/swingline{unique}.csv'.format(
                dirpath=os.path.abspath(arg_dict.rpt_dir), unique=opt_dict['tstamp']),
                             'json_file': '{dirpath}/swingline{unique}.json'.format(
                                 dirpath=os.path.abspath(arg_dict.rpt_dir), unique=opt_dict['tstamp']),
                             'xlsx_file': '{dirpath}/swingline{unique}.xlsx'.format(
                                 dirpath=os.path.abspath(arg_dict.rpt_dir), unique=opt_dict['tstamp']),
                             'summary_file': '{dirpath}/swingline{unique}.txt'.format(
                                 dirpath=os.path.abspath(arg_dict.rpt_dir), unique=opt_dict['tstamp'])})
        else:
            RUNTIME_LOG.warning(
                'Invalid reports directory arguement "{arg}" - using default'.format(arg=arg_dict.rpt_dir))

    return opt_dict


def parse_opt_temp(arg_dict, opt_dict):
    """ PARSE OPT TEMP function """
    if arg_dict.tmp_dir and not 'default' in arg_dict.tmp_dir:
        if os.path.exists(arg_dict.log_dir):
            opt_dict['tmp_dir'] = os.path.abspath(arg_dict.tmp_dir)
        else:
            RUNTIME_LOG.warning(
                'Invalid temporary directory arguement "{arg}" - using default'.format(arg=arg_dict.tmp_dir))

    return opt_dict


def parse_opt_logging(arg_dict, opt_dict):
    """ PARSE OPT LOGGING function """
    if arg_dict.log_dir and not 'default' in arg_dict.log_dir:
        if os.path.exists(arg_dict.log_dir):
            opt_dict['log'] = os.path.abspath(arg_dict.log_dir)
            ## Create FILE logging destination - incl. for VDIAG
            logfile_vdiag = logging.handlers.TimedRotatingFileHandler(
                '{path}/{file}'.format(path=os.path.abspath(arg_dict.log_dir), file='swingline.log'),
                when='d',
                interval=1,
                backupCount=7,
                delay=False,
                utc=True)
            logfile_vdiag.setFormatter(FMT_LOG_DEFAULT)
            RUNTIME_LOG.addHandler(logfile_vdiag)
            RUNTIME_LOG.removeHandler(CONSOLE)
            RUNTIME_LOG.removeHandler(LOCALHOST)
            RUNTIME_LOG.setLevel(logging.DEBUG)
            RUNTIME_LOG.debug(
                'vDiag environment variable VDIAG_LOGDIR overrides defaults - new log file path "{path}"'.format(
                    path=os.path.abspath(arg_dict.log_dir)))
        else:
            RUNTIME_LOG.warning(
                'Invalid vm-support bundle extracted directory arguement "{arg}" - using default'.format(
                    arg=arg_dict.bundle_dir))

    if arg_dict.debug:
        RUNTIME_LOG.removeHandler(LOCALHOST)
        RUNTIME_LOG.setLevel(logging.DEBUG)
    if arg_dict.silent:
        RUNTIME_LOG.removeHandler(CONSOLE)
    if arg_dict.quiet:
        RUNTIME_LOG.setLevel(logging.WARNING)

    return opt_dict


def track_use(status):
    """  LOG METRIC function """
    log_message = '{status} "{ver}", "{ssh}","{cwd}","{user}","{script}"'.format(status=status.upper(),
                                                                                 ver=__version__,
                                                                                 ssh=os.getenv('SSH_CONNECTION'),
                                                                                 cwd=os.getcwd(),
                                                                                 user=os.getenv('USER'),
                                                                                 script=sys.argv[0:])
    if 'start' in status.lower():
        USAGE_TRACKING.info(log_message)
        RUNTIME_LOG.debug(log_message)
        RUNTIME_LOG.info('Swingline version {ver} - {script}'.format(ver=__version__, script=sys.argv[0:]))
    elif 'stop' in status.lower():
        USAGE_TRACKING.info(log_message)
        RUNTIME_LOG.debug(log_message)
        RUNTIME_LOG.info('Swingline Complete')


def insert_sample():
    """  INSERT SAMPLE function """
    ## Intialize db table with sample event(s)
    ##  Avoids missing category felds in sql queries
    ##  Provide built-in KB documentation in results
    TBL_STORAGE.insert(
        dict(category='iofails', date='1970-01-01', hour='00', time='00:00:00.000Z', host='example.local',
             fname='example.log', dev='naa.0123456789abcdef0123456789abcdef', dsname='ExampleDatastore',
             world='vmkernel', cmd='0xff', t10='T10_XLATE', sense='H:GOOD D:GOOD P:GOOD',
             asense='H:0x0 D:0x0 P:0x0 Valid sense data: 0x0 0x0 0x0',
             raw='VMW KB 289902: Interpreting SCSI sense codes in VMware ESXi and ESX, http://kb.vmware.com/kb/289902'))
    TBL_STORAGE.insert(
        dict(category='sioclmt', date='1970-01-01', hour='00', time='00:00:00.000Z', host='example.local',
             fname='example.log', dev='naa.0123456789abcdef0123456789abcdef', dsname='ExampleDatastore',
             world='vmguest', cmd='0xff', t10='T10_XLATE',
             raw='VMW KB 1038241: Limiting disk I/O from a specific virtual machine, http://kb.vmware.com/kb/1038241'))
    TBL_STORAGE.insert(
        dict(category='latency', date='1970-01-01', hour='00', time='00:00:00.000Z', host='example.local',
             fname='example.log', dev='naa.0123456789abcdef0123456789abcdef', dsname='ExampleDatastore',
             world='vmguest', latency='0', lavg='0',
             raw='VMW KB 2007236: Storage device performance deteriorated, http://kb.vmware.com/kb/2007236'))
    TBL_STORAGE.insert(
        dict(category='apdpdls', date='1970-01-01', hour='00', time='00:00:00.000Z', host='example.local',
             fname='example.log', dev='naa.0123456789abcdef0123456789abcdef', dsname='ExampleDatastore',
             world='vmkernel', cmd='(ALL)', t10='(ALL)', latency='APD/PDL',
             raw='VMW KB 2004684: Permanent Device Loss (PDL) and All-Paths-Down (APD) in vSphere 5.x, http://kb.vmware.com/kb/2004684'))


def pop_db(path):
    """ POPULATE DATABASE function """
    ## Assign pat_dns pattern for uname result - used to find ESXi hostname
    ## Assign pat_txt pattern for vmkernel logs - used to find storage events
    ## Assign pat_gzt pattern for compressed vmkernel logs - used to find storage events
    ## Assign pat_dev pattern for vmfs to device mappings  - used to find datastore name
    ## Assign pat_header for matching (and skipping) header
    ## Assign pat_dir to optimize file checks by limiting paths - elimiate weird copies
    pat_dict = {'dns': re.compile(r'^uname_-a.txt'),
                'txt': re.compile(r'^(vmkernel|vobd)(\.log|\.[0-9]+(?!\.gz))'),
                'gz': re.compile(r'^(vmkernel|vobd)\.[0-9]+\.gz'),
                'vmfs': re.compile(r'^localcli_storage-vmfs-extent-list.txt'),
                'header': re.compile(r'^Volume Name.*|^--*$'),
                'subdir': re.compile(r'/(var|commands)/')}
    ## Assign a default, empty hostnname
    esxi_dict = {'bundle': '', 'uname': '', 'alt': ''}

    ## Process the files in order (topdown) a single path (root, dirs, files)
    ##  Incl. symbolic links (important for automated extraction workarounds)
    for root, dirs, files in os.walk(path, topdown=True, followlinks=True):
        ## Check the number of '/'s (os.sep) against
        ##  variable max_depth and truncate dirs if exceeded
        if root.count(os.sep) >= 32:
            del dirs[:]
            RUNTIME_LOG.warning('Reached maximum directory depth - depth {depth}'.format(depth=32))
        ## Process all the files - could use optimizing, meh
        for fname in files:
            esxi_dict['root'] = root
            esxi_dict['fname'] = fname
            esxi_dict = parse_file(esxi_dict, pat_dict)

    ## Complete all writes to db - all ops are read from this point
    DB.commit()


def parse_file(esxi_dict, pat_dict):
    """ PARSE FILE function  """
    ## Assign variable fullaname the file's full path name
    ##  variable path already normalized,
    ##  could use normalize again, but no problems found
    ## Check variable fullname is not a symlink
    ##  there should not be any symlinks,
    ##  but it has happened and caused exceptions
    ## The os.walk data is alphabetically sorted with topdown=True, and
    ##  All directories at the same level are processed BEFORE the next
    ##  level down. So ./commands is processed before ./var, and
    ##  /etc/vmware is later than both because it is a deeper layer.
    ##  All directories at the same level are processed BEFORE the next level down.
    if (pat_dict['dns'].search(esxi_dict['fname']) or pat_dict['txt'].search(esxi_dict['fname']) or pat_dict[
        'gz'].search(esxi_dict['fname']) or pat_dict['vmfs'].search(esxi_dict['fname'])) and pat_dict['subdir'].search(
            os.path.abspath(os.path.join(esxi_dict['root'], esxi_dict['fname']))) and not os.path.islink(
            os.path.abspath(os.path.join(esxi_dict['root'], esxi_dict['fname']))):
        # Assign variable 'bundle' the vm-support directory name for later logging
        esxi_dict['bundle'] = re.sub(r'^.*/esx-', 'esx-',
                                     os.path.abspath(os.path.join(esxi_dict['root'], esxi_dict['fname'])).lower())
        esxi_dict['bundle'] = re.sub(r'/.*$', '', esxi_dict['bundle'])
        esxi_dict['alt'] = re.sub(r'.*(esx-.*-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]--[0-9][0-9]\.[0-9][0-9]).*',
                                  r'\1', os.path.abspath(os.path.join(esxi_dict['root'], esxi_dict['fname'])).lower())
        esxi_dict['alt'] = re.sub(r'(esx-|-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]--[0-9][0-9]\.[0-9][0-9])', '',
                                  esxi_dict['alt'])

        RUNTIME_LOG.debug('Processing vm-support "{dirpath}" - file "{file}"'.format(file=esxi_dict['fname'],
                                                                                     dirpath=esxi_dict['bundle']))
        ## Capture the ESXi hostname for logging
        ##  with each event from this vm-support bundle
        ## Check variable name mathes ./commands/uname_-a.txt
        ##  using regex is overkill, but used for consistency
        ##   with later vmkernel name matching that is required
        if pat_dict['dns'].search(esxi_dict['fname']):
            esxi_dict = parse_file_dns(esxi_dict)
        ## Capture the datastore names and extents (storage devices)
        ##  in dict 'esxi_dict' for logging with each event from this
        ##  vm-support bundle
        ## Check variable name mathes
        ##  ./commands/localcli_storage-vmfs-extent-list.txt
        ##  using regex is overkill, but used for consistency (again)
        elif pat_dict['vmfs'].search(esxi_dict['fname']):
            esxi_dict = parse_file_vmfs(esxi_dict, pat_dict)
        ## Capture the events from ALL vmkernel logs
        ##  (.log, .all, .[0-9] and .[0-9].gz)
        elif pat_dict['txt'].search(esxi_dict['fname']):
            parse_file_txt(esxi_dict)
        elif pat_dict['gz'].search(esxi_dict['fname']):
            parse_file_gz(esxi_dict)

    return esxi_dict


def parse_file_dns(esxi_dict):
    """ PARSE FILE DNS function """
    ## Open the file handle to read the file content
    ##  'with' automagically closes filehandle (neat)
    with open(os.path.abspath(os.path.join(esxi_dict['root'], esxi_dict['fname'])), "r") as fileopen:
        for line in fileopen:
            ## Check hostname attribute in uname_-a.txt
            ##  do more error checking and logging to verify
            if 'VMkernel ' in line:
                esxi_dict['uname'] = re.sub(r'VMkernel | .*$', '', line.strip()).lower()
    if not esxi_dict['uname']:
        RUNTIME_LOG.debug('Missing vm-support bundle "{dirpath}" uname file "{file} - using hostname "{host}"'.format(
            host=esxi_dict['alt'], dirpath=esxi_dict['bundle'], file='uname_-a.txt'))

    return esxi_dict


def parse_file_vmfs(esxi_dict, pat_dict):
    """ PARSE FILE VMFS function """
    ## Open the file handle to read the file content
    with open(os.path.abspath(os.path.join(esxi_dict['root'], esxi_dict['fname'])), "r") as fileopen:
        for line in fileopen:
            if not pat_dict['header'].search(line):
                ## Check device (extent) and datastore listing
                ##  use regex to capture dsnames with spaces
                extent = re.sub(r'^.*  *[0-9a-f]*-[0-9a-f]*-[0-9a-f]*-[0-9a-f]*  *[0-9]  *|  *[0-9]  *$', '',
                                line).strip()
                datastore = re.sub(r'  *[0-9a-f]*-[0-9a-f]*-[0-9a-f]*-[0-9a-f]*  *[0-9]  *.*  *[0-9]  *$', '',
                                   line).strip()
                if extent and datastore:
                    esxi_dict[extent] = datastore
                else:
                    RUNTIME_LOG.debug(
                        'Missing information from vm-support "{dirpath}" - vmfs extent file "{file}'.format(
                            dirpath=esxi_dict['bundle'], file='localcli_storage-vmfs-extent-list.txt'))
    return esxi_dict


def parse_file_txt(esxi_dict):
    """ PARSE FILE TXT function """
    # esxi_dict = parse_file_txt(esxi_dict, pat_dict)
    ## Check variable hostname is assigned and use N/A if not
    ##  ./commands/uname_-a.txt missing or incomplete (weird)
    if not esxi_dict['uname']:
        esxi_dict['uname'] = esxi_dict['alt']
    ## Open a read-only file handle
    with open(os.path.abspath(os.path.join(esxi_dict['root'], esxi_dict['fname'])), "r") as fileopen:
        for line in fileopen:
            ## Call function insert_rec
            ##  parses the hostname and line (logged event)
            ##  into db fields and inserts
            insert_rec(esxi_dict, line)


def parse_file_gz(esxi_dict):
    """ PARSE FILE gz function """
    ## Check variable hostname is assigned and use N/A if not
    ## uname_-a.txt missing or incomplete (again, weird)
    if not esxi_dict['uname']:
        esxi_dict['uname'] = esxi_dict['alt']
    ## Open a GZip read-only file handle
    ##  unlike 'with' requires requesting close because GZip
    fileopen = gzip.GzipFile(os.path.abspath(os.path.join(esxi_dict['root'], esxi_dict['fname'])), "r")
    for line in fileopen:
        ## Call function insert_rec - parses the hostname and
        ##  line (logged event) into db fields and inserts
        insert_rec(esxi_dict, str(line))
    fileopen.close()


def insert_rec(esxi_dict, line):
    """ INSERT DATABASE RECORD function """
    pat_dict = {'datetime': re.compile(r'[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]{3}Z'),
                'latency': re.compile(r'performance has deteriorated'),
                'dupvobd': re.compile(r'vob.scsi.device.io.latency.high'),
                'iofails': re.compile(
                    r'ScsiDeviceIO\: [0-9]+\: Cmd\(0x[0-9a-fA-F]+\) 0x[0-9a-fA-F][0-9a-fA-F], CmdSN 0x[0-9a-fA-F]+ from world [0-9]+ to dev .* failed .* sense data: '),
                'iosmart': re.compile(r' Cmd\(0x[0-9a-fA-F]+\) 0x(1a|4d|85), '),
                'sioclmt': re.compile(r'ScsiDeviceIO.* Restricting cmd .* from WID [0-9]+ to quiesced dev'),
                'apdpdls': re.compile(r'ScsiDevice.* Device .* APD Notify PERM LOSS; token num:[0-9]+')}

    if pat_dict['datetime'].match(line):
        line = re.sub(r'"|\n|\r|$', '', line.strip())
        msg_dict = {'date': line[0:10],
                    'hour': line[11:13],
                    'time': line[11:24]}
        if pat_dict['apdpdls'].search(line):
            # From OpenGrok.eng.vmware.com xref: /vsphere60u1.perforce/vsphere60u1/vmkernel/storage/device/scsi_device.c
            msg_dict.update({'cat': 'apdpdls',
                             'ext': re.sub(r'^.* Device | APD.*', '', line),
                             'msec': 'APD/PDL',
                             'world': 'vmkernel',
                             'cmd': '(ALL)',
                             't10': '(ALL)'})
            msg_dict['dsn'] = esxi_dict.get(msg_dict['ext'], 'N/A')
            # RUNTIME_LOG.debug('apdpdl -  msg "{msg}"'.format(msg=msg_dict))
            try:
                TBL_STORAGE.insert(dict(category=msg_dict['cat'], host=esxi_dict['uname'], fname=esxi_dict['fname'],
                                        date=msg_dict['date'], hour=msg_dict['hour'], time=msg_dict['time'],
                                        world=msg_dict['world'], cmd=msg_dict['cmd'], t10=msg_dict['t10'],
                                        dev=msg_dict['ext'], dsname=msg_dict['dsn'], latency=msg_dict['msec'],
                                        raw=line))
            except RuntimeError:
                RUNTIME_LOG.warning('Failed creating record from message "{msg}[...]"'.format(msg=line[36:116]))

        elif pat_dict['iofails'].search(line) and not pat_dict['iosmart'].search(line):
            # From OpenGrok.eng.vmware.com xref: /vsphere60u1.perforce/vsphere60u1/vmkernel/storage/device/scsi_device_io.c
            world = re.sub(r'^.*CmdSN 0x[0-9a-fA-F]+ from world | to dev .*$', '', line)
            if world == '0':
                world = 'vmkernel'
            else:
                world = 'vmguest'

            msg_dict.update({'cat': 'iofails',
                             'cmd': re.sub(
                                 r'^.* Cmd\(0x[0-9a-fA-F]+\) |, CmdSN 0x[0-9a-fA-F]+ from world [0-9]+ to dev .*$', '',
                                 line),
                             # 'world': re.sub(r'^.*CmdSN 0x[0-9a-fA-F]+ from world | to dev .*$', '', line),
                             'world': world,
                             'ext': re.sub(r'^.* to dev | failed .*$', '', line),
                             'asense': re.sub(r'^.* failed |\.$', '', line)})
            msg_dict.update({'t10': xlate_t10_cmd(msg_dict['cmd']),
                             'dsn': esxi_dict.get(msg_dict['ext'], 'N/A'),
                             'sense': xlate_t10_sense(re.sub(r' (Possible|Valid).*$', '', msg_dict['asense']))})
            # RUNTIME_LOG.debug('iofails - msg "{msg}"'.format(msg=msg_dict))
            try:
                TBL_STORAGE.insert(dict(category=msg_dict['cat'], host=esxi_dict['uname'], fname=esxi_dict['fname'],
                                        date=msg_dict['date'], hour=msg_dict['hour'], time=msg_dict['time'],
                                        cmd=msg_dict['cmd'], t10=msg_dict['t10'], world=msg_dict['world'],
                                        dev=msg_dict['ext'], dsname=msg_dict['dsn'], sense=msg_dict['sense'],
                                        asense=msg_dict['asense'], raw=line))
            except RuntimeError:
                RUNTIME_LOG.warning('Failed creating record from message "{msg}[...]"'.format(msg=line[36:116]))

        elif pat_dict['latency'].search(line) and not pat_dict['dupvobd'].search(line):
            # From OpenGrok.eng.vmware.com xref: /vsphere60u1.perforce/vsphere60u1/vmkernel/storage/device/scsi_device_io.c
            msg_dict.update({'cat': 'latency',
                             'ext': re.sub(r'^.* Device | performance has deteriorated.*$', '', line),
                             'msec': re.sub(r'^.* value of [0-9]+ microseconds to ', '', line),
                             'mavg': re.sub(r'^.* value of | microseconds to [0-9]+.*$', '', line)})
            msg_dict.update({'dsn': esxi_dict.get(msg_dict['ext'], 'N/A'),
                             'msec': re.sub(r' .*', '', msg_dict['msec'])})
            # RUNTIME_LOG.debug('latency - msg "{msg}"'.format(msg=msg_dict))
            try:
                TBL_STORAGE.insert(dict(category=msg_dict['cat'], host=esxi_dict['uname'], fname=esxi_dict['fname'],
                                        date=msg_dict['date'], hour=msg_dict['hour'], time=msg_dict['time'],
                                        dev=msg_dict['ext'], dsname=msg_dict['dsn'], latency=msg_dict['msec'],
                                        lavg=msg_dict['mavg'], raw=line))
            except RuntimeError:
                RUNTIME_LOG.warning('Failed creating record from message "{msg}[...]"'.format(msg=line[36:116]))

        elif pat_dict['sioclmt'].search(line):
            # From OpenGrok.eng.vmware.com xref: /vsphere60u1.perforce/vsphere60u1/vmkernel/storage/device/scsi_device_io.c
            world = re.sub(r'^.* from WID | to quiesced dev .*$', '', line)
            if world == '0':
                world = 'vmkernel'
            else:
                world = 'vmguest'

            msg_dict.update({'cat': 'sioclmt',
                             'cmd': re.sub(r'^.* Restricting cmd | \([0-9]+ bytes\) .*$', '', line),
                             # 'world': re.sub(r'^.* from WID | to quiesced dev .*$', '', line),
                             'world': world,
                             'ext': re.sub(r'^.* to quiesced dev |:[0-9]+ \(vmkCmd=0x.*$', '', line)})
            msg_dict.update({'t10': xlate_t10_cmd(msg_dict['cmd']),
                             'dsn': esxi_dict.get(msg_dict['ext'], 'N/A')})
            # RUNTIME_LOG.debug('sioclmt - msg "{msg}"'.format(msg=msg_dict))
            try:
                TBL_STORAGE.insert(dict(category=msg_dict['cat'], host=esxi_dict['uname'], fname=esxi_dict['fname'],
                                        date=msg_dict['date'], hour=msg_dict['hour'], time=msg_dict['time'],
                                        cmd=msg_dict['cmd'], t10=msg_dict['t10'], world=msg_dict['world'],
                                        dev=msg_dict['ext'], dsname=msg_dict['dsn'], raw=line))
            except RuntimeError:
                RUNTIME_LOG.warning('Failed creating record from message "{msg}[...]"'.format(msg=line[36:116]))


def check_db():
    """ CHECK DATABASE function """
    for tbl_name in DB.tables:
        tbl_len = len(DB[tbl_name])
        if tbl_len > 4:
            RUNTIME_LOG.info(
                'Captured dataset - table "{table}", records "{count}"'.format(table=tbl_name, count=tbl_len))
        else:
            RUNTIME_LOG.warning(
                'Empty dataset - table "{table}", records "{count}" (should be > 4 records)'.format(table=tbl_name,
                                                                                                    count=tbl_len))
            RUNTIME_LOG.info(
                'Empty dataset situation 1 - No block storage performance events exist (storage is NFS or local "mpx.C#.T#.L#"?)')
            RUNTIME_LOG.info(
                'Empty dataset situation 2 - ESXi vm-support bundle file or directory permissions (wrx on vm-bundle?)')
            RUNTIME_LOG.info('Empty dataset situation 3 - ESXi vm-support bundle file or directory match failed (bug?)')
            sys.exit(1)


def relocate_file(file_src, file_dst):
    """ RELOCATE RESULTS FILE function """
    file_src = os.path.abspath(file_src)
    file_dst = os.path.abspath(file_dst)
    file_exists = os.path.isfile(file_src)

    if file_exists:
        # os.chmod(file_src, 0644)

        if file_src == file_dst:
            RUNTIME_LOG.info('Moved results to "{dst}" - exists {exists}, size {size}'.format(dst=file_dst, exists=str(
                file_exists).lower(), size=os.path.getsize(file_dst)))
        else:
            try:
                shutil.move(file_src, file_dst)
                RUNTIME_LOG.info('Moved results to "{dst}" - exists {exists}, size {size}'.format(dst=file_dst,
                                                                                                  exists=str(
                                                                                                      file_exists).lower(),
                                                                                                  size=os.path.getsize(
                                                                                                      file_dst)))
            except RuntimeError:
                RUNTIME_LOG.info(
                    'Failed moving dataset freeze - temporary file "{src}" exists {exist}, destination file "{dst}" exists false'.format(
                        src=file_src, exists=str(file_exists).lower(), dst=file_dst))
    else:
        RUNTIME_LOG.error('Failed moving dataset freeze - temporary file "{tmp}", exists false'.format(tmp=file_src))


def freeze_tbl(freeze_setup):
    """ FREEZE DATABASE TABLE function """
    freeze_format = freeze_setup['format']
    freeze_export_file = freeze_setup['freeze_file']
    sql_query = freeze_setup['sql_query']

    # export all data into a single CSV or JSON
    # NOTE: freeze_export_tmp has to be in CWD/PWD - dataset cannot handle full paths
    freeze_export_tmp = os.path.basename(freeze_export_file)

    result = []

    try:
        result = DB.query(sql_query)
    except RuntimeError:
        RUNTIME_LOG.error('Failed dataset query "{qry}" for {fmt} query'.format(qry=sql_query, fmt=freeze_format))

    if result:
        # RUNTIME_LOG.debug('Completed dataset {fmt} query - SQL "{qry}"'.format(qry=sql_query, fmt=freeze_format))
        # NOTE: freeze_export_tmp has to be in CWD/PWD - dataset cannot handle full paths
        dataset.freeze(result, format=freeze_format, filename=freeze_export_tmp)
        relocate_file(freeze_export_tmp, freeze_export_file)


def freeze_summary(freeze_setup):
    """ FREEZE TOP TEN SUMMARY RESULTS function """
    freeze_export_file = freeze_setup['opt_dict']['summary_file']
    sql_dict = freeze_setup['sql_dict']

    freeze_export_file = os.path.abspath(freeze_export_file)
    freeze_export_tmp = '{path}/{file}'.format(path=freeze_setup['opt_dict']['tmp_dir'],
                                               file=os.path.basename(freeze_export_file))

    file_handle = open(freeze_export_tmp, 'w')
    file_handle.write('Top Ten Summary for multiple vm-support bundles...')
    pat_omitkey = re.compile(r'(id|raw|latency|lavg|time|asense)')

    for category in ('iofails', 'sioclmt', 'latency', 'apdpdls'):
        sql_query = sql_dict[category]
        sql_query = sql_query + ' LIMIT 1'
        sql_query = re.sub(r'time', 'hour', sql_query)
        sql_query = re.sub(r'asense', 'sense', sql_query)

        result = []
        try:
            result = DB.query(sql_query)
            # RUNTIME_LOG.debug('Completed dataset {fmt} query - SQL "{qry}"'.format(qry=sql_query, fmt=freeze_format))
        except RuntimeError:
            RUNTIME_LOG.error('Failed dataset {fmt} query - SQL "{qry}"'.format(qry=sql_query, fmt='summary'))

        key_list = {}
        for record in result:
            for key in record.keys():
                key = re.sub(r'(^u\'|\'$)', '', str(key))
                if not key in key_list:
                    key_list[key] = ''

        for key in key_list:
            if not pat_omitkey.match(key):
                result = []
                sql_query = 'SELECT {field}, COUNT(*) c FROM {table} WHERE category=\'{cat}\' AND date<>\'1970-01-01\' GROUP BY {field} ORDER BY c DESC, {field} LIMIT 10'.format(
                    field=key, cat=category, table='storage')

                try:
                    result = DB.query(sql_query)
                except RuntimeError:
                    RUNTIME_LOG.error(
                        'Failed dataset query for top ten summary {field} values - SQL "{sql}"'.format(field=key,
                                                                                                       sql=sql_query))
                if result:
                    file_handle.write('\n\n### {table} summary for {key} ###\n'.format(table=category, key=key))
                    for record in result:
                        value = record[key]
                        count = record[u'c']
                        file_handle.write('{c}\t{v}\n'.format(c=str(count).rjust(10), v=value))

    file_handle.flush()  # <-- buffers write to disk for accurate size
    # file_handle.closed

    relocate_file(freeze_export_tmp, freeze_export_file)


def freeze_xlsx_incl(workbook, freeze_incl_file):
    """ FREEZE XLSX INCL function """
    if os.path.isfile(freeze_incl_file):
        format_summary = workbook.add_format({'num_format': '0', 'align': 'center'})
        summarysheet = workbook.add_worksheet('summary')
        summarysheet.set_column(0, 1, 50, format_summary)
        # RUNTIME_LOG.debug('Importing into XLSX "{dst}" - worksheet "{sheet}", file "{src}"'.format(src=freeze_incl_file, sheet='summary', dst=freeze_export_file))
        with open(freeze_incl_file, "r") as fileopen:
            row = 0
            pat_not_header = re.compile(r'\t')
            for line in fileopen:
                line = re.sub(r'^\t+', '', line.strip())
                if pat_not_header.search(line):
                    count = re.sub(r'\t.*$', '', line)
                    if count.isdigit():
                        count = int(count)
                    summarysheet.write(row, 0, count)
                    value = re.sub(r'^.*\t', '', line)
                    # if value.isdigit():
                    #    value = int(value)
                    summarysheet.write(row, 1, value)
                else:
                    summarysheet.write(row, 0, line)
                    # summarysheet.write(row, 1, line)
                row += 1


def freeze_xlsx(freeze_setup):
    """ FREEZE MICROSOFT EXCEL SPREADSHEET function """
    freeze_export_tmp = '{path}/{file}'.format(path=freeze_setup['opt_dict']['tmp_dir'],
                                               file=os.path.basename(freeze_setup['opt_dict']['xlsx_file']))

    workbook = xlsxwriter.Workbook(freeze_export_tmp)

    freeze_xlsx_incl(workbook, freeze_setup['opt_dict']['summary_file'])

    worksheet = workbook.add_worksheet('event')
    result = []
    try:
        result = DB.query(freeze_setup['sql_query'])
        # RUNTIME_LOG.debug('Completed dataset {fmt} query - SQL "{qry}"'.format(qry=freeze_setup['sql_query'], fmt='xlsx'))
    except RuntimeError:
        RUNTIME_LOG.error('Failed dataset {fmt} query - SQL "{qry}"'.format(qry=freeze_setup['sql_query'], fmt='xlsx'))

    # col_widths = {}
    # col_order = {}
    # row = 1
    # col_chr = 'A'
    # col_hdr = 0
    wks_dict = {'row': 1, 'widths': {}, 'order': {}, 'alpha': 'A', 'hdr': 0}
    for record in result:
        col = 0
        for key, value in record.items():
            key = re.sub(r'(^u\'|\'$)', '', str(key))
            value = re.sub(r'(^u\'|\'$)', '', str(value))
            if not key in wks_dict['widths']:
                wks_dict['order'][wks_dict['alpha']] = key
                wks_dict['widths'][key] = 15
                worksheet.write(0, wks_dict['hdr'], key)
                wks_dict['alpha'] = chr(ord(wks_dict['alpha']) + 1)
                wks_dict['hdr'] += 1
            if wks_dict['widths'][key] < len(value):
                wks_dict['widths'][key] = len(value) + 5
            if ('latency' or 'lavg' or 'world' in key) and value.isdigit():
                worksheet.write_number(wks_dict['row'], col, int(value))
            else:
                worksheet.write(wks_dict['row'], col, value)
            col += 1
        wks_dict['row'] += 1

    wks_dict['row_final'] = wks_dict['row'] - 1
    wks_dict['col_final'] = col - 1

    freeze_xlsx_format({'workbook': workbook,
                        'worksheet': worksheet,
                        'wks_dict': wks_dict})
    workbook.close()

    relocate_file(freeze_export_tmp, freeze_setup['opt_dict']['xlsx_file'])


def freeze_xlsx_format(format_setup):
    """ FREEZE XLSX FORMAT function """
    format_header = format_setup['workbook'].add_format({'bold': True, 'italic': True, 'underline': True})
    format_date = format_setup['workbook'].add_format({'num_format': 'yyyy-mm-dd'})
    format_number = format_setup['workbook'].add_format({'num_format': '0'})
    format_apdpdls = format_setup['workbook'].add_format({'bg_color': '#FF0000'})
    format_txtnone = format_setup['workbook'].add_format({'fg_color': '#808080', 'bg_color': '#D3D3D3'})

    format_setup['worksheet'].set_row(0, None, format_header)
    # Format column format_setup['wks_dict']['widths'] for date,time,host,dev,latency,raw
    for key in format_setup['wks_dict']['order'].keys():
        if 'date' in format_setup['wks_dict']['order'][key]:
            alpha = '{alpha}:{alpha}'.format(alpha=key)
            format_setup['worksheet'].set_column(alpha, format_setup['wks_dict']['widths'][
                format_setup['wks_dict']['order'][key]], format_date)
        elif 'latency' in format_setup['wks_dict']['order'][key]:
            tag_heatmap = key
            alpha = '{alpha}:{alpha}'.format(alpha=key)
            format_setup['worksheet'].set_column(alpha, format_setup['wks_dict']['widths'][
                format_setup['wks_dict']['order'][key]], format_number)
        else:
            alpha = '{alpha}:{alpha}'.format(alpha=key)
            format_setup['worksheet'].set_column(alpha, format_setup['wks_dict']['widths'][
                format_setup['wks_dict']['order'][key]])

    ## Format autofilter on columns date,time,host,dev,latency,raw
    format_setup['worksheet'].autofilter(0, 0, format_setup['wks_dict']['row_final'],
                                         format_setup['wks_dict']['col_final'])
    ## Freeze top row with headers and autofilter
    format_setup['worksheet'].freeze_panes(1, 0)
    ## Format conditional fomatting
    fm_cond_range = '{col}2:{col}{row}'.format(col=tag_heatmap, row=format_setup['wks_dict']['row_final'] + 1)
    format_setup['worksheet'].conditional_format(fm_cond_range,
                                                 {'type': '3_color_scale',
                                                  'min_color': '#00FF00',
                                                  'mid_color': '#FFFF00',
                                                  'max_color': '#FF0000'})
    format_setup['worksheet'].conditional_format(fm_cond_range,
                                                 {'type': 'text',
                                                  'criteria': 'containing',
                                                  'value': 'APD/PDL',
                                                  'format': format_apdpdls})
    format_setup['worksheet'].conditional_format(fm_cond_range,
                                                 {'type': 'text',
                                                  'criteria': 'containing',
                                                  'value': 'None',
                                                  'format': format_txtnone})

    tag_heatmap = chr(ord(tag_heatmap) + 1)
    fm_cond_range = '{col}2:{col}{row}'.format(col=tag_heatmap, row=format_setup['wks_dict']['row_final'] + 1)
    format_setup['worksheet'].conditional_format(fm_cond_range,
                                                 {'type': '3_color_scale',
                                                  'min_color': '#00FF00',
                                                  'mid_color': '#FFFF00',
                                                  'max_color': '#FF0000'})


def milton_waddams():
    """ EASTER EGG function """
    #     Milton Waddams: Excuse me, I believe you have my stapler...
    RUNTIME_LOG.debug('Excuse me, I believe you have my stapler...')


def xlate_t10_cmd(cmd_hex):
    """" TRANSLATE SCSI COMMAND HEXT CODES TO T10 HUMAN READABLE function """
    ## See references at:
    ##    http://www.vmware.com/files/pdf/techpaper/VMware-vSphere-Storage-API-Array-Integration.pdf
    ##    www.t10.org/lists/op-num.htm

    t10_dict = {"0x00": "TEST_UNIT_READY",
                "0x01": "REWIND/REZERO_UNIT_[SBC]",
                "0x02": "T10_UNSPECIFIED",
                "0x03": "REQUEST_SENSE",
                "0x04": "FORMAT_MEDIUM/FORMAT_UNIT/FORMAT",
                "0x05": "READ_BLOCK_LIMITS",
                "0x06": "T10_UNSPECIFIED",
                "0x07": "INITIALIZE_ELEMENT_STATUS/REASSIGN_BLOCKS",
                "0x08": "GET_MESSAGE/READ/RECEIVE",
                "0x09": "T10_UNSPECIFIED",
                "0x0a": "PRINT/SEND_MESSAGE/SEND/WRITE",
                "0x0b": "SEEK_[SBC]/SET_CAPACITY/SLEW_AND_PRINT",
                "0x0c": "T10_UNSPECIFIED",
                "0x0d": "T10_UNSPECIFIED",
                "0x0e": "T10_UNSPECIFIED",
                "0x0f": "READ_REVERSE",
                "0x10": "SYNCHRONIZE_BUFFER/WRITE_FILEMARKS",
                "0x11": "SPACE",
                "0x12": "INQUIRY",
                "0x13": "VERIFY",
                "0x14": "RECOVER_BUFFERED_DATA",
                "0x15": "MODE_SELECT",
                "0x16": "RESERVE_ELEMENT_[SMC]/RESERVE_[SPC-2]",
                "0x17": "RELEASE_ELEMENT_[SMC]/RELEASE_[SPC-2]",
                "0x18": "COPY_[SPC]",
                "0x19": "ERASE",
                "0x1a": "MODE_SENSE/[ignore_S.M.A.R.T.]",
                "0x1b": "LOAD_UNLOAD/OPEN/CLOSE_IMPORT/EXPORT_ELEMENT/SCAN/START_STOP_UNIT/STOP_PRINT",
                "0x1c": "RECEIVE_DIAGNOSTIC_RESULTS",
                "0x1d": "SEND_DIAGNOSTIC",
                "0x1e": "PREVENT_ALLOW_MEDIUM_REMOVAL",
                "0x1f": "T10_UNSPECIFIED",
                "0x20": "T10_UNSPECIFIED",
                "0x21": "T10_UNSPECIFIED",
                "0x22": "T10_UNSPECIFIED",
                "0x23": "READ_FORMAT_CAPACITIES",
                "0x24": "SET_WINDOW",
                "0x25": "GET_WINDOW/READ_CAPACITY/READ_CAPACITY/READ_CARD_CAPACITY",
                "0x26": "T10_UNSPECIFIED",
                "0x27": "T10_UNSPECIFIED",
                "0x28": "GET_MESSAGE/READ",
                "0x29": "READ_GENERATION",
                "0x2a": "SEND_MESSAGE/SEND/WRITE",
                "0x2b": "LOCATE/POSITION_TO_ELEMENT/SEEK_[SBC]",
                "0x2c": "ERASE",
                "0x2d": "READ_UPDATED_BLOCK",
                "0x2e": "WRITE_AND_VERIFY",
                "0x2f": "VERIFY",
                "0x30": "SEARCH_DATA_HIGH_[SBC]",
                "0x31": "OBJECT_POSITION/SEARCH_DATA_EQUAL_[SBC]",
                "0x32": "SEARCH_DATA_LOW_[SBC]",
                "0x33": "SET_LIMITS_[SBC]",
                "0x34": "GET_DATA_BUFFER_STATUS/PRE-FETCH/READ_POSITION",
                "0x35": "SYNCHRONIZE_CACHE",
                "0x36": "LOCK_UNLOCK_CACHE_[SBC]",
                "0x37": "INITIALIZE_ELEMENT_STATUS_WITH_RANGE/READ_DEFECT_DATA",
                "0x38": "MEDIUM_SCAN",
                "0x39": "COMPARE_[SPC]",
                "0x3a": "COPY_AND_VERIFY_[SPC]",
                "0x3b": "WRITE_BUFFER",
                "0x3c": "READ_BUFFER",
                "0x3d": "UPDATE_BLOCK",
                "0x3e": "READ_LONG",
                "0x3f": "WRITE_LONG",
                "0x40": "CHANGE_DEFINITION_[SPC]",
                "0x41": "WRITE_SAME",
                "0x42": "READ_SUB-CHANNEL/UNMAP_(VAAI)",
                "0x43": "READ_TOC/PMA/ATIP",
                "0x44": "READ_HEADER/REPORT_DENSITY_SUPPORT",
                "0x45": "PLAY_AUDIO",
                "0x46": "GET_CONFIGURATION",
                "0x47": "PLAY_AUDIO_MSF",
                "0x48": "SANITIZE",
                "0x49": "T10_UNSPECIFIED",
                "0x4a": "GET_EVENT_STATUS_NOTIFICATION",
                "0x4b": "PAUSE/RESUME",
                "0x4c": "LOG_SELECT",
                "0x4d": "LOG_SENSE/[ignore_S.M.A.R.T.]",
                "0x4e": "STOP_PLAY/SCAN",
                "0x4f": "T10_UNSPECIFIED",
                "0x50": "XDWRITE_[SBC-2]",
                "0x51": "READ_DISC_INFORMATION/XPWRITE",
                "0x52": "READ_TRACK_INFORMATION/XDREAD_[SBC-2]",
                "0x53": "RESERVE_TRACK/XDWRITEREAD",
                "0x54": "SEND_OPC_INFORMATION",
                "0x55": "MODE_SELECT",
                "0x56": "RESERVE_ELEMENT_[SMC]/RESERVE_[SPC-2]",
                "0x57": "RELEASE_ELEMENT_[SMC]/RELEASE_[SPC-2]",
                "0x58": "REPAIR_TRACK",
                "0x59": "T10_UNSPECIFIED",
                "0x5a": "MODE_SENSE",
                "0x5b": "CLOSE_TRACK/SESSION",
                "0x5c": "READ_BUFFER_CAPACITY",
                "0x5d": "SEND_CUE_SHEET",
                "0x5e": "PERSISTENT_RESERVE_IN",
                "0x5f": "PERSISTENT_RESERVE_OUT",
                "0x7e": "extended_CDB",
                "0x7f": "variable_length_CDB_(more_than_16_bytes)",
                "0x80": "WRITE_FILEMARKS/XDWRITE_EXTENDED_[SBC]",
                "0x81": "READ_REVERSE/REBUILD_[SBC]",
                "0x82": "ALLOW_OVERWRITE/REGENERATE_[SBC]",
                "0x83": "Third-party_Copy_OUT_(VAAI_XCopy)",
                "0x84": "Third-party_Copy_IN",
                "0x85": "ATA_PASS-THROUGH/[ignore_S.M.A.R.T.]",
                "0x86": "ACCESS_CONTROL_IN",
                "0x87": "ACCESS_CONTROL_OUT",
                "0x88": "READ",
                "0x89": "COMPARE_AND_WRITE_(VAAI_ATS)",
                "0x8a": "WRITE",
                "0x8b": "ORWRITE",
                "0x8c": "READ_ATTRIBUTE",
                "0x8d": "WRITE_ATTRIBUTE",
                "0x8e": "WRITE_AND_VERIFY",
                "0x8f": "VERIFY",
                "0x90": "PRE-FETCH",
                "0x91": "SPACE/SYNCHRONIZE_CACHE",
                "0x92": "LOCATE/LOCK_UNLOCK_CACHE_[SBC]",
                "0x93": "ERASE/WRITE_SAME_(VAAI_Zero)",
                "0x94": "SCSI_Socket_Services_project",
                "0x95": "SCSI_Socket_Services_project",
                "0x96": "SCSI_Socket_Services_project",
                "0x97": "SCSI_Socket_Services_project",
                "0x98": "T10_UNSPECIFIED",
                "0x99": "T10_UNSPECIFIED",
                "0x9a": "T10_UNSPECIFIED",
                "0x9b": "T10_UNSPECIFIED",
                "0x9c": "WRITE_ATOMIC",
                "0x9d": "SERVICE_ACTION_BIDIRECTIONAL",
                "0x9e": "SERVICE_ACTION_IN",
                "0x9f": "SERVICE_ACTION_OUT",
                "0xa0": "REPORT_LUNS",
                "0xa1": "ATA_PASS-THROUGH/BLANK",
                "0xa2": "SECURITY_PROTOCOL_IN",
                "0xa3": "MAINTENANCE_IN/SEND_KEY",
                "0xa4": "MAINTENANCE_OUT/REPORT_KEY",
                "0xa5": "MOVE_MEDIUM_[SMC-2]/PLAY_AUDIO",
                "0xa6": "EXCHANGE_MEDIUM/LOAD/UNLOAD_C/DVD",
                "0xa7": "MOVE_MEDIUM_ATTACHED_[SMC-2]/SET_READ_AHEAD",
                "0xa8": "GET_MESSAGE/READ",
                "0xa9": "SERVICE_ACTION_OUT",
                "0xaa": "SEND_MESSAGE/WRITE",
                "0xab": "SERVICE_ACTION_IN",
                "0xac": "ERASE/GET_PERFORMANCE",
                "0xad": "READ_DVD_STRUCTURE",
                "0xae": "WRITE_AND_VERIFY",
                "0xaf": "VERIFY",
                "0xb0": "SEARCH_DATA_HIGH_[SBC]",
                "0xb1": "SEARCH_DATA_EQUAL_[SBC]",
                "0xb2": "SEARCH_DATA_LOW_[SBC]",
                "0xb3": "SET_LIMITS_[SBC]",
                "0xb4": "READ_ELEMENT_STATUS_ATTACHED_[SMC-2]",
                "0xb5": "REQUEST_VOLUME_ELEMENT_ADDRESS/SECURITY_PROTOCOL_OUT",
                "0xb6": "SEND_VOLUME_TAG/SET_STREAMING",
                "0xb7": "READ_DEFECT_DATA",
                "0xb8": "READ_ELEMENT_STATUS_[SMC-2]",
                "0xb9": "READ_CD_MSF",
                "0xba": "REDUNDANCY_GROUP_(IN)/SCAN",
                "0xbb": "REDUNDANCY_GROUP_(OUT)/SET_CD_SPEED",
                "0xbc": "SPARE_(IN)",
                "0xbd": "MECHANISM_STATUS/SPARE_(OUT)",
                "0xbe": "READ_CD/VOLUME_SET_(IN)",
                "0xbf": "SEND_DVD_STRUCTURE/VOLUME_SET_(OUT)",
                "0xfe": "Third-party_GENERIC_(VAAI_ATS)"}

    try:
        cmd_t10 = t10_dict[cmd_hex]
        return cmd_t10
    except RuntimeError:
        RUNTIME_LOG.debug('Failed translating SCSI hexadecimal command "{cmd}" to T10 name'.format(cmd=cmd_hex))
        return "T10_UNSPECIFIED"


def xlate_t10_sense(sense):
    """ TRANSLATE SCSI SENSE HEX CODES TO T10 HUMAN READABLE function """
    ## See references at:
    ##    https://gsstools.vmware.com/tools/scsi-decoder/
    ##    http://kb.vmware.com/kb/289902

    sense_low = sense.lower()
    pat_hex = re.compile(r'0x[0-9a-fA-F]+')
    h_sense = re.sub(r'^h:', '', sense_low)
    h_sense = re.sub(r' .*', '', h_sense)
    d_sense = re.sub(r'^.*d:', '', sense_low)
    d_sense = re.sub(r' .*', '', d_sense)
    p_sense = re.sub(r'^.*p:', '', sense_low)
    p_sense = re.sub(r' .*', '', p_sense)

    if pat_hex.match(h_sense) and pat_hex.match(d_sense) and pat_hex.match(p_sense):
        h_dict = {"0x0": "GOOD",
                  "0x1": "NO_CONNECT",
                  "0x2": "BUS_BUSY",
                  "0x3": "TIME_OUT",
                  "0x4": "BAD_TARGET",
                  "0x5": "ABORT",
                  "0x6": "PARITY",
                  "0x7": "ERROR",
                  "0x8": "RESET",
                  "0x9": "BAD_INTR",
                  "0xa": "PASSTHROUGH",
                  "0xb": "SOFT_ERROR",
                  "0xc": "IMM_RETRY",
                  "0xd": "REQUEUE"}

        d_dict = {"0x0": "GOOD",
                  "0x2": "CHECK_CONDITION",
                  "0x4": "CONDITION_MET",
                  "0x8": "BUSY",
                  "0x10": "INTERMEDIATE",
                  "0x14": "INTERMEDIATE-CONDITION_MET",
                  "0x18": "RESERVATION_CONFLICT",
                  "0x22": "Obsolete",
                  "0x28": "TASK_SET_FULL",
                  "0x30": "ACA_ACTIVE",
                  "0x40": "TASK_ABORTED"}

        p_dict = {"0x0": "GOOD",
                  "0x1": "TRANSIENT",
                  "0x2": "SNAPSHOT",
                  "0x3": "RESERVATION_LOST",
                  "0x4": "REQUEUE",
                  "0x5": "ATS_MISCOMPARE",
                  "0x6": "THINPROV_BUSY_GROWING",
                  "0x7": "THINPROV_ATQUOTA",
                  "0x8": "THINPROV_NOSPACE"}

        try:
            h_t10 = h_dict[h_sense]
            d_t10 = d_dict[d_sense]
            p_t10 = p_dict[p_sense]
            hdp_t10 = "H:{h} D:{d} P:{p}".format(h=h_t10, d=d_t10, p=p_t10)
            return hdp_t10
        except RuntimeError:
            RUNTIME_LOG.warning('Failed translating SCSI sense code "{sense}" to T10 names'.format(sense=sense))
            return sense
    else:
        RUNTIME_LOG.warning(
            'Failed translating sense codes to T10 text - sense "H:{h} D:{d} P:{p}"'.format(h=h_sense, d=d_sense,
                                                                                            p=p_sense))
        return sense


if __name__ == '__main__':
    main()

# EOF
