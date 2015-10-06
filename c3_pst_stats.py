#!python
#pylint: disable=line-too-long, logging-format-interpolation

""" Convert Microsoft Outlook .PST files to .TXT
using Python for Windows Extensions from http://sourceforge.net/projects/pywin32/
and counts totals for:
 FROM: email address (various)
 TO: email address c3-monitor@vmware.com
 VMware Cloud Command Center (C3) Error IDs
"""

__author__ = 'jantonacci'
__version__ = '2.7.0' # first release was cmd.exe batch file

import os, sys,logging,time, re, codecs
from win32com.client import Dispatch

def main():
    """
    :desc  : main function
    :rtype : file
    """
    # Set the default options in main dictionary
    main_dict = default_options()

    main_dict = clr_summation(main_dict)
    main_dict['olfolder'] = folder_path(main_dict['non_emea'])
    main_dict = msg_summation(main_dict)
    report_c3err(main_dict)

    main_dict = clr_summation(main_dict)
    main_dict['olfolder'] = folder_path(main_dict['non_nasa'])
    main_dict = msg_summation(main_dict)
    report_c3err(main_dict)

def clr_summation(main_dict):
    main_dict['email'] = {}
    main_dict['c3err'] = {}
    return main_dict

def msg_summation(main_dict):
    olfolder = main_dict['olfolder'].Name
    msg_queue = main_dict['olfolder'].Items
    main_dict['email'].update({'Total Messages': msg_queue.Count})
    pat_c3err = re.compile(r'\[Log Insight\].*C3ErrorID:[1-6][0-9][0-9][0-9]')

    index = 1
    msg = msg_queue.GetFirst()
    while msg:
        if pat_c3err.match(msg.Subject):
            if main_dict['email'].has_key(msg.SenderEmailAddress.lower()):
                main_dict['email'][msg.SenderEmailAddress.lower()] += 1
            else:
                main_dict['email'][msg.SenderEmailAddress.lower()] = 1
            subj_count = int(re.sub(r'^\[Log Insight\] |\+* new events* found for alert: C3ErrorID:.*$', '', msg.Subject))
            subj_key = '{s}|{e}'.format(s=msg.SenderEmailAddress.lower(),
                                        e=re.sub(r'^.*C3ErrorID:| .*$', '', msg.Subject).strip())
            if main_dict['c3err'].has_key(subj_key):
                if subj_count:
                    main_dict['c3err'][subj_key] = main_dict['c3err'][subj_key] + subj_count
                    RUNTIME_LOG.debug('Adding {v} to {k}'.format(k=subj_key, v=subj_count))
                else:
                    main_dict['c3err'][subj_key] += 1
                    RUNTIME_LOG.debug('Incrementing to {k}'.format(k=subj_key))
            else:
                if subj_count:
                    main_dict['c3err'][subj_key] = subj_count
                    RUNTIME_LOG.debug('Creating {k} as {v}'.format(k=subj_key, v=subj_count))
                else:
                    main_dict['c3err'][subj_key] = 1
                    RUNTIME_LOG.debug('Creating {k} as 1'.format(k=subj_key))
        RUNTIME_LOG.info('Processing "{f}" item {i} of {t}: "{k}" (+{v})'.format(f=olfolder, i=index, t=msg_queue.Count, k=subj_key, v=subj_count))
        if index > msg_queue.Count + 10:
            RUNTIME_LOG.warning('Processed more items than item count: {i} of {t} (weird).  Break loop.'.format(i=index, t=msg_queue.Count))
            break
        msg = msg_queue.GetNext()
        index += 1

    return main_dict

def report_c3err(main_dict):
    """
    :desc  : Generate the report from main dictionary lists email and c3err
    :rtype : int
    """
    with open(main_dict['fpath_c3_rprt_txt'], 'a') as file_rpt:
        file_rpt.write('Date/Time:\t{str}\n'.format(str=main_dict['tstamp']))
        file_rpt.write('Outlook Folder:\t{str}\n'.format(str=main_dict['olfolder'].Name))
        file_rpt.write('\nC3 Alert totals by sender...\n')
        for key in sorted(main_dict['email'].keys()):
            file_rpt.write('{k}:\t{v}\n'.format(k=key, v=main_dict['email'][key]))

        file_rpt.write('\nC3 Alert totals by sender and error ID...\n')
        for key in sorted(main_dict['c3err'].keys()):
            file_rpt.write('{k}:\t{v}\n'.format(k=key, v=main_dict['c3err'][key]))

        file_rpt.write('\n')

    file_rpt.close()
    return 0

def folder_path(olfolder_path):
    olns = connect_profile(olfolder_path[0])
    shared_account = find_folder(olfolder_path[1], olns)
    shared_inbox = find_folder(olfolder_path[2], shared_account)
    shared_subfolder = find_folder(olfolder_path[3], shared_inbox)
    #print '"{n}": {c}'.format(n=shared_subfolder.Name, c=shared_subfolder.Items.Count)
    RUNTIME_LOG.info('Outlook folder "{n}" has item count {c}'.format(n=shared_subfolder.Name, c=shared_subfolder.Items.Count))
    return shared_subfolder

def connect_profile(profile):
    # Connect to Outlook, which has to be running
    try:
        olns = Dispatch("Outlook.Application").GetNamespace("MAPI")
        # Leave .Logon undefined to use default Mail profile (MAPI)
        olns.Logon(profile)
        return olns
    except:
        RUNTIME_LOG.error('Outlook MAPI profile connection failed')
        sys.exit(1)

def find_folder(target_folder, parent_folder):
    try:
        for folder in parent_folder.Folders:
            folder_name = DECODEUNICODESTRING(folder.Name)
            if folder_name == target_folder:
                return folder
        return None
    except RuntimeError as error:
        print (error)
        return None

def msg_iterate(folder):
    messages = folder.Items
    #message = messages.GetFirst()
    message = messages.GetLast()
    while message:
        msg_from = message.SenderEmailAddress
        msg_subj = message.Subject
        print 'FROM:\t{f}\n\tSubject:\t{s}'.format(f=msg_from, s=msg_subj)
        message = messages.GetNext()

def print_c3err(main_dict):
    """
    :desc  : Print the report from function report_c3err
    :rtype : int
    """
    file_rpt = open(main_dict['fpath_c3_rprt_txt'], 'r')

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
                 'dir_msg_dst': os.path.abspath(os.path.join(os.environ['USERPROFILE'],'Desktop')),
                 'non_emea': ['Non-EMEA', 'c3-mbx-1', 'Inbox', '5. Non-EMEA'],
                 'non_nasa': ['Non-NASA', 'c3-mbx-2', 'Inbox', '5. Non-NASA'],
                 'olfolder': '',
                 'email': {},
                 'c3err': {}}

    main_dict.update({'fpath_c3_rprt_txt': os.path.join(main_dict['dir_msg_dst'], '{u}-c3msgstats.txt'.format(u=main_dict['tstamp']))})

    return main_dict

if __name__ == '__main__':
    DECODEUNICODESTRING = lambda x: codecs.latin_1_encode(x)[0]
    WORKING_DIR = r'c:\opt\c3_py'
    ORIG_DIR = os.curdir

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

    os.chdir(WORKING_DIR)
    main()
    os.chdir(ORIG_DIR)

#EOF
