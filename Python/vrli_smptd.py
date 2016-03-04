#!/usr/bin/python
# pylint: disable=indexing-exception
""" Use TCP sockets to test SMTP with packet capture """
import logging
import multiprocessing
import socket
from random import randint
from subprocess import call, Popen
from sys import argv, exit
from time import sleep, strftime


def main():
    """ Main function...
    setup tcpdump packet captures,
    run SMTP connection(s),
    then tear down tcpdump """
    pcap_dict = do_pcap()
    smtpd_listen(RUNTIME_SEC)
    undo_pcap(pcap_dict)
    RUNTIME_LOG.info('Main function exit')
    exit(0)

def smtpd_listen(runtime_sec):
    """ Listen TCP socket as if SMTP server """
    RUNTIME_LOG.info('SMTP daemon starting {h}:{p} (timeout={t1}s, exit={t2}s)'.format(h='localhost', p=SMTPPORT, t1=TIMEOUT_MAX, t2=runtime_sec))
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.bind(('localhost', SMTPPORT))
    tcp_listen = 20
    tcp_socket.listen(tcp_listen)

    workers = [multiprocessing.Process(target=smtpd_reply, args=(tcp_socket,)) for i in range(tcp_listen)]

    for p in workers:
        p.daemon = True
        p.start()

    sleep(runtime_sec)
    RUNTIME_LOG.info('SMTP daemon exit {h}:{p}'.format(h='localhost', p=SMTPPORT))
    return 0

def smtpd_reply(tcp_socket):
    delay = randint(TIMEOUT_MIN,TIMEOUT_MAX)
    RUNTIME_LOG.debug('SMTP daemon listening')
    while True:
        client, address = tcp_socket.accept() #accept the connection
        RUNTIME_LOG.info('SMTP client connected {h}:{p} - {s} seconds before response'.format(h=address[0], p=address[1], s=delay))
        sleep(delay)
        client.send('220 {name}\r\n'.format(name=socket.getfqdn()))
        RUNTIME_LOG.info('SMTP 220 inital server respopnse to {h}:{p} - {s} second delay'.format(h=address[0], p=address[1], s=delay))
        client.close()

def do_pcap():
    """ Install tcpdump RPM and start two packet captures """
    RUNTIME_LOG.info('Installing tcpdump RPM and starting captures (text and packet)')
    RUNTIME_LOG.info('If exceptions may prevent packet capture cleanup, run... \n\tfor PROC in $(ps -ef | grep tcpdump | grep -v grep | awk \'\{print $2\}\'); do kill $PROC; done\n')
    call(["/etc/gss_support/install.sh"])

    pcap_dict = {}

    pcap_log = open('{path}/{file}{unique}.txt'.format(path=DIRPATH, file=TEMPLATE, unique=DATETIME), 'wb')
    pcap_dict['log'] = pcap_log
    pcap_dict['pcap1'] = Popen(['tcpdump',
                                           '-anUlpvvs0',
                                           'tcp port {p}'.format(p=SMTPPORT)],
                                          stdout=pcap_log)

    pcap_bin = '{file}{unique}.pcap'.format(file=TEMPLATE, unique=DATETIME)
    pcap_dict['pcap2'] = Popen(['tcpdump',
                                           '-anUlps0',
                                           '-w{file}'.format(file=pcap_bin),
                                           'tcp port {p}'.format(p=SMTPPORT)],
                                          cwd=DIRPATH,
                                          close_fds=True,
                                          bufsize=-1)

    sleep(5)

    return pcap_dict

def undo_pcap(pcap_dict):
    """ Terminate packet captures and uninstall tcpdump RPM """
    # TODO: for PROC in $(ps -ef | grep tcpdump | grep -v grep | awk '{print $2}'); do kill $PROC; done
    RUNTIME_LOG.info('Stopping packet capture and uninstalling tcpdump RPM')
    pcap_dict['pcap1'].terminate()
    pcap_dict['pcap2'].terminate()
    pcap_dict['pcap2'].wait()
    pcap_dict['log'].flush()
    pcap_dict['log'].close()
    pcap_dict['pcap1'].kill()
    pcap_dict['pcap1'].kill()
    call(["/etc/gss_support/uninstall.sh"])

if __name__ == '__main__':
    if argv[1:]:
        RUNTIME_SEC = int(argv[1])   # This can be IP or DNS
    else:
        print '\nUsage: {file} <seconds>\n'.format(file=__file__)
        exit(1)

    SMTPPORT = 50025   # SMTP TCP port - SSL/TLS not supported
    TIMEOUT_MAX = 300  # TCP daemon connection timeout - RFC 2821 spec
    TIMEOUT_MIN = 5    # TCP client connection timeout - vRLI Java SMTP
    DIRPATH = '/c3'
    TEMPLATE = 'smtpd-cnxn'
    DATETIME = strftime("-%Y%m%d-%H%M%S")

    ## Create a new instance named RUNTIME_LOG - separate from root and customize
    RUNTIME_LOG = logging.getLogger('RUNTIME_LOG')
    ## Setup logging to flexibly handle script progress notices and exceptions from
    ## module logging.  Create logging message and date format instance for common
    ## use ammong multiple logging destinations.
    FMT_LOG_DEFAULT = logging.Formatter('%(asctime)s.%(msecs)03d PID%(process)d:%(levelname)-8s:%(filename)s:%(funcName)-15s:%(message)s', '%Y-%m-%dT%H:%M:%S')
    ## Create STDERR logging destination - incl. for BRB and development
    CONSOLE = logging.StreamHandler()
    CONSOLE.setFormatter(FMT_LOG_DEFAULT)
    LOGFILE = logging.FileHandler('{path}/{file}{unique}.log'.format(path=DIRPATH, file=TEMPLATE, unique=DATETIME))
    LOGFILE.setFormatter(FMT_LOG_DEFAULT)
    RUNTIME_LOG.addHandler(CONSOLE)
    RUNTIME_LOG.addHandler(LOGFILE)
    RUNTIME_LOG.setLevel(logging.DEBUG)

    main()

#EOF
