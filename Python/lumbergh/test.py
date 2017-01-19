#!/usr/bin/env python3
import inspect
import logging
import os
import re

import lumbergh


def get():
    file_list = []
    for file_name in os.listdir('test_files'):
        file_list.append('test_files/{f}'.format(f=file_name))
    # print(file_list)
    return file_list


def suite():
    level = logging.DEBUG
    file_list = get()
    # file_list = ['test_files/lipsum-short.txt.gz',
    #              'test_files/lipsum-short.sha1',
    #              'test_files/lipsum-short.txt',
    #              'lipsum.bad']
    file_name_ok = ['test_files/lipsum-short.txt.gz']
    file_name_bad = ['lipsum.bad']
    str_list = ['Generated']
    re_list = [re.compile(r'^generated', re.IGNORECASE)]
    # print(file_list)
    l = lumbergh.Logger(stdout=False, system=False, usage=False, level=level)
    print(sorted([attr for attr in dir(l) if inspect.ismethod(getattr(l, attr))]))
    b = lumbergh.Base(file=file_list, level=level)
    print(sorted([attr for attr in dir(b) if inspect.ismethod(getattr(b, attr))]))
    # ['__call__', 'c_keys', 'c_replace', 'c_search', 'f_search']
    print('\n###\tc_keys\t###')
    print(b.c_keys())
    # print('\n###\tc_values\t###')
    # print(b.c_values())
    print('\n###\tc_search string\t###')
    print(b.c_search(string=str_list))
    print('\n###\tc_search regex\t###')
    print(b.c_search(regex=re_list))
    print('\n###\tc_search file_name\t###')
    print(b.c_search(file=file_name_ok))
    print('\n###\tc_search bad_file_name\t###')
    print(b.c_search(file=file_name_bad))
    print('\n###\tc_search string file_name\t###')
    print(b.c_search(string=str_list, file=file_name_ok))
    print('\n###\tc_search string bad_file_name\t###')
    print(b.c_search(string=str_list, file=file_name_bad))
    print('\n###\tc_replace string => c_search default => f_search\t###')
    b.c_replace(string=str_list)
    print(b.c_search())
    b.f_search(file=file_list)
    print('\n###\tc_replace regex => c_search default => f_search\t###')
    b.c_replace(regex=re_list)
    print(b.c_search())


if __name__ == "__main__":
    get()
    suite()
