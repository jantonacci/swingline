#!python
#pylint: disable=line-too-long

""" Convert Microsoft Outlook .MSG files to .TXT
and count totals for:
 FROM: email address (various)
 TO: email address c3-monitor@vmware.com
 VMware Cloud Command Center (C3) Error IDs
"""

__author__ = 'jantonacci'
__version__ = '2.0' # first release was cmd.exe batch file

import os, sys, time, logging, re, hashlib, shutil, subprocess, multiprocessing

WORKING_DIR = 'c:\opt\c3_py'

## Setup logging to flexibly handle script progress notices and exceptions from
## module logging.  Create logging message and date format instance for common
## use ammong multiple logging destinations.
FMT_LOG_DEFAULT = logging.Formatter('%(asctime)s.%(msecs)03d PID%(process)d:%(levelname)-8s:%(filename)s:%(funcName)-15s:%(message)s', '%Y-%m-%dT%H:%M:%S')

## Create STDERR logging destination - incl. for BRB and development
CONSOLE = logging.StreamHandler()
CONSOLE.setFormatter(FMT_LOG_DEFAULT)

## Create a new instance named RUNTIME_LOG - separate from root and customize
RUNTIME_LOG = logging.getLogger('RUNTIME_LOG')
#RUNTIME_LOG.setLevel(logging.DEBUG)
RUNTIME_LOG.setLevel(logging.INFO)
RUNTIME_LOG.addHandler(CONSOLE)

def main():
    """
    :desc  : main function
    :rtype : file
    """
    # Set the default options in main dictionary
    main_dict = default_options()

    # Find Outlook messages (.MSG) and update main dictionary
    main_dict.update({'msg_list': find_msg(main_dict)})

    # Convert Outlook messages (.MSG) to text (.TXT)
    #
    main_dict = cnvrt_msg(main_dict)

    main_dict['email'], main_dict['c3err'] = find_c3err(main_dict)

    report_c3err(main_dict)
    print_c3err(main_dict)

def cnvrt_msg(main_dict):
    """
    :desc  : msgtext.exe conversion and update main dictionary with text (.TXT) file name list
    :rtype : dict
    """
    file_log = open(main_dict['fpath_c3_cnvrt_log'],'w')
    txt_list = []

    print 'Converting Outlook messages ',
    for file_msg in main_dict['msg_list']:
        hash_msg = hashlib.sha1(file_msg).hexdigest()[-8:]
        subprocess.call([main_dict['msgtext_exe'],
                         file_msg,
                         '{u}.txt'.format(u=os.path.join(main_dict['dir_msg_txt'], hash_msg))],
                          stdout=file_log,
                          stderr=file_log)
        print '.',
        txt_list.append('{u}.txt'.format(u=os.path.join(main_dict['dir_msg_txt'], hash_msg)))
        try:
            shutil.move(file_msg, os.path.join(main_dict['dir_msg_dst'], '{u}.msg'.format(u=hash_msg)))
        except RuntimeWarning:
            RUNTIME_LOG.error('Failed moving message "{s}" to "d"'.format(s=file_msg,
                                                                          d=os.path.join(main_dict['dir_msg_dst'],
                                                                                                   '{u}.msg'.format(u=hash_msg))))
            break
    print '.'

    file_log.close()
    main_dict.update({'txt_list': txt_list})
    return main_dict

def find_c3err(main_dict):
    email_dict = {'c3-monitor@vmware.com': len(main_dict['txt_list'])}
    c3err_dict = {}

    for txt_file in main_dict['txt_list']:
        with open(txt_file, "r") as fileopen:
            for line in fileopen:
                if line.startswith('From: '):
                    email_from = re.sub(r'^.*<|>.*$', '', line).lower().strip()
                    if email_dict.has_key(email_from):
                        email_dict[email_from] += 1
                    else:
                        email_dict[email_from] = 1
                if line.startswith('Subject: ') and 'C3ErrorID:' in line:
                    subj_count = int(re.sub(r'^Subject: \[Log Insight\] |\+* new events* found for alert: C3ErrorID:.*$', '', line))
                    #subj_errid = re.sub(r'^.*C3ErrorID:| .*$', '', line).strip()
                    subj_key = '{s}|{e}'.format(s=email_from, e=re.sub(r'^.*C3ErrorID:| .*$', '', line).strip())
                    if c3err_dict.has_key(subj_key):
                        if subj_count:
                            c3err_dict[subj_key] = c3err_dict[subj_key] + subj_count
                            RUNTIME_LOG.debug('Adding {v} to {k}'.format(k=subj_key, v=subj_count))
                        else:
                            c3err_dict[subj_key] += 1
                            RUNTIME_LOG.debug('Incrementing to {k}'.format(k=subj_key))
                    else:
                        if subj_count:
                            c3err_dict[subj_key] = subj_count
                            RUNTIME_LOG.debug('Creating {k} as {v}'.format(k=subj_key, v=subj_count))
                        else:
                            c3err_dict[subj_key] = 1
                            RUNTIME_LOG.debug('Creating {k} as 1'.format(k=subj_key))

    return email_dict, c3err_dict

def report_c3err(main_dict):

    file_rpt = open(main_dict['fpath_c3_rprt_txt'],'w')

    file_rpt.write('Date/Time:\t{str}\n'.format(str=main_dict['tstamp']))
    file_rpt.write('Message Destination:\t{str}\n'.format(str=main_dict['dir_msg_dst']))
    file_rpt.write('Text    Destination:\t{str}\n'.format(str=main_dict['dir_msg_txt']))

    file_rpt.write('\nC3 Alert totals by sender...')
    for key in sorted(main_dict['email'].keys()):
        file_rpt.write('{k}:\t{v}\n'.format(k=key, v=main_dict['email'][key]))

    file_rpt.write('\nC3 Alert totals by sender and error ID...\n')
    for key in sorted(main_dict['c3err'].keys()):
        file_rpt.write('{k}:\t{v}\n'.format(k=key, v=main_dict['c3err'][key]))

    file_rpt.close()

    return 0

def print_c3err(main_dict):
    file_rpt = open(main_dict['fpath_c3_rprt_txt'],'r')

    for line in file_rpt:
        print line

    file_rpt.close()

    return 0

def default_options():
    """
    :desc  : Create dictionary of runtime options for later reference
    :rtype : dict
    """
    main_dict = {'tstamp': time.strftime("%Y%m%d-%H%M%S"),
                'dir_bin': os.path.abspath('.'),
                'msgtext_exe': os.path.join('.', 'msgtext.exe'),
                'dir_msg_src': os.path.join('.', 'msg_src'),
                'email': '',
                'c3err': ''}

    main_dict.update({'dir_msg_dst': os.path.join(main_dict['dir_msg_src'], os.path.join(main_dict['tstamp'], 'msg_bin')),
                      'dir_msg_txt': os.path.join(main_dict['dir_msg_src'], os.path.join(main_dict['tstamp'], 'msg_txt'))})

    main_dict.update({'fpath_c3_rprt_txt': os.path.join(main_dict['dir_msg_src'], '{u}-c3msgstats.txt'.format(u=main_dict['tstamp'])),
                      'fpath_c3_cnvrt_log': os.path.join(main_dict['dir_msg_txt'], '{u}-c3msgcnvrt.log'.format(u=main_dict['tstamp']))})

    return main_dict

def check_dir(main_dict):
    """
    :desc  : Validate directories exist and in certain cases, create them
    :rtype : int
    """
    if not os.path.exists(main_dict['dir_msg_src']):
        RUNTIME_LOG.error('Failed reading source directory for Outlook exported messages (.MSG) - "{s}"'.format(s=main_dict['dir_msg_src']))
        sys.exit(1)
    if not os.path.exists(main_dict['dir_msg_dst']):
        try:
            os.makedirs(main_dict['dir_msg_dst'])
        except RuntimeError:
            RUNTIME_LOG.error('Failed creating destination directory for original messages (.MSG) - "{s}"'.format(s=main_dict['dir_msg_dst']))
            sys.exit(1)
    if not os.path.exists(main_dict['dir_msg_txt']):
        try:
            os.makedirs(main_dict['dir_msg_txt'])
        except RuntimeError:
            RUNTIME_LOG.error('Failed creating destination directory for converted messages (.TXT) - "{s}"'.format(s=main_dict['dir_msg_txt']))
            sys.exit(1)

    return 0

def find_msg(main_dict):
    """
    :desc  : Find absolute paths and file names for Outlook messages in source directory, no sub-dirs
    :rtype : list, bool
    """
    msg_list = []
    for fname in os.listdir(main_dict['dir_msg_src']):
        if fname.endswith(".msg"):
            msg_list.append(os.path.join(main_dict['dir_msg_src'], fname))

    if len(msg_list) > 1:
        check_dir(main_dict)
        return msg_list
    else:
        RUNTIME_LOG.error('Failed finding Outlook messages (.MSG) in "{s}"'.format(s=main_dict['dir_msg_src']))
        sys.exit(1)

if __name__ == '__main__':
    """
    :desc  :   Call main function
    """
    dir_current = os.curdir
    os.chdir(WORKING_DIR)
    main()
    os.chdir(dir_current)
#EOF
