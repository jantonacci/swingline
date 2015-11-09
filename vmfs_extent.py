#!/usr/bin/env python
#pylint: disable=line-too-long
""" Insert extent names into report results for VMFS versions """

import os, re, sys


def main():
    """ Call functions and print results to STDOUT"""
    ## Check file dependencies are met or quit
    file_check(RPT_TXT)
    ## Create a list from the report results file (global variable)
    vmfs_list = parse_file_tdlog(RPT_TXT)
    ## Create a dictionary for extents and datastores
    vmfs_dict = parse_file_vmfs()
    ## Substitute datastore and extent name for just datastore in report
    result_list = mergemergemerge(vmfs_dict, vmfs_list)

    ## Show results
    for line in result_list:
        print line

def file_check(report_result):
    """ Check file dependencies are met or quit """
    try:
        RPT_TXT=sys.argv[1]
    except:
        print 'USAGE: {f} <RPT_TXT result file>\n\nCurrent directory should be extracted ESXi vm-support bundle.'.format(f=__file__)
        quit()

    if not os.path.isfile(report_result) and os.path.isfile('./commands/localcli_storage-vmfs-extent-list.txt'):
        print 'Directory "{d}" \n\tdoes not contain report result "{f}" OR "./commands/localcli_storage-vmfs-extent-list.txt"\n'.format(d=os.path.abspath('.'), f=RPT_TXT)
        print 'Please make sure:\n\t"." is an extracted ESXi vm-support bundle\n\treport has been run\n\treport result inlcuded as command line option\n'
        quit()

def parse_file_tdlog(report_result):
    """ PARSE FILE RPT_TXT function
    parse_file_tdlog(report_result) -> vmfs_list
    """
    ## Create an empty list to populate and then return
    vmfs_list = []
    ## Open the file handle to read the file content
    with open(report_result, "r") as fileopen:
        ## Process each line in the file
        for line in fileopen:
            ## if the line contains a VMFS version like 'VMFS-5.60'
            if re.compile(r'VMFS-[0-9]\.[0-9][0-9]').search(line):
                ## Substitute leading white space with nothing
                re.sub(r'^  *', '', line)
                ## Append the line to the list and remove any
                ##  trailing white space or newline (strip)
                vmfs_list.append(line.strip())
    ## Results to main
    return vmfs_list

def parse_file_vmfs():
    """ PARSE FILE VMFS function
    parse_file_vmfs() -> vmfs_dict
    """
    ## Create an empty dictionary to populate and then return
    vmfs_dict = {}
    ## Open the file handle to read the file content
    with open('./commands/localcli_storage-vmfs-extent-list.txt', "r") as fileopen:
        ## Process each line in the file
        for line in fileopen:
            ## Skip the header line
            if not re.compile(r'^Volume Name.*|^--*$').search(line):
                ## Check device (extent) and datastore listing
                ##  use regex to capture dsnames with spaces
                extent = re.sub(r'^.*  *[0-9a-f]*-[0-9a-f]*-[0-9a-f]*-[0-9a-f]*  *[0-9]  *|  *[0-9]  *$', '', line).strip()
                datastore = re.sub(r'  *[0-9a-f]*-[0-9a-f]*-[0-9a-f]*-[0-9a-f]*  *[0-9]  *.*  *[0-9]  *$', '', line).strip()
                ## If both variables are defined,
                ##  add them as a new key (extent) and value (datastore)
                if extent and datastore:
                    vmfs_dict[extent] = datastore
    ## Results to main
    return vmfs_dict

def mergemergemerge(vmfs_dict, vmfs_list):
    """ Substitute datastore and extent for datastore
    mergemergemerge(vmfs_dict, vmfs_list) -> result_list
    """
    # Sample line:
    # '        VMFS-5.60     datastore1 (1)                        public           Mon Apr 27 14:27:15 2015  yes             UNKNOWN'
    ## Create an empty list to populate and then return
    result_list = []
    ## Open the file handle to read the file content
    for line in vmfs_list:
        ## Process each (key, value) pair in the dictionary
        for extent, datastore in vmfs_dict.iteritems():
            ## If the line contains a datastore,
            ##  substitute the datastore name with formatted key and value
            ##  and append to the list
            if datastore in line:
                result_list.append(re.sub(datastore, '"{d}"\t{e}'.format(d=datastore,e=extent), line))
    ## Results to main
    return result_list


if __name__ == '__main__':
    RPT_TXT=''
    main()

#EOF
