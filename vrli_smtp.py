#!/usr/bin/python
# pylint: disable=indexing-exception
""" Use TCP sockets to test SMTP with packet capture """
import socket, sys, time, re, subprocess, logging

def main():
    """ Main function...
    setup tcpdump packet captures,
    run SMTP connection(s),
    then tear down tcpdump """
    pcap_dict = do_pcap()
    #smtp_cnxn('localhost')
    smtp_cnxn(SMTPHOST)
    undo_pcap(pcap_dict)
    sys.exit(0)

def smtp_cnxn(hostname):
    """ Establish TCP socket connection to an SMTP server """
    RUNTIME_LOG.info('SMTP service check for {h}:{p} (timeout={t}s)'.format(h=hostname, p=SMTPPORT, t=TIMEOUT))
    tcp_socket = socket.create_connection((hostname, SMTPPORT), TIMEOUT)
    log_reply(tcp_socket)
    smtp_queue(tcp_socket)
    tcp_socket.close()

def smtp_queue(tcp_socket):
    """ Queue a series of SMTP commands (verbs) and exit on error """
    verb_list = ['EHLO {name}'.format(name=socket.getfqdn()),
                 'RSET',
                 'HELO {name}'.format(name=socket.getfqdn()),
                 'NOOP',
                 'MAIL FROM:<c3-admin@{name}>'.format(name=socket.getfqdn()),
                 'RCPT TO:<c3-monitor@vmware.com>',
                 'DATA',
                 'Subject: {file} - C3 vRLI SMTP test\r\n{file} - C3 vRLI SMTP test\r\n.'.format(file=__file__),
                 'QUIT']
    for verb in verb_list:
        socket_error = smtp_exec(tcp_socket, verb)
        if not socket_error == 0:
            break

def smtp_exec(tcp_socket, smtp_cmd):
    """ Execute individual SMTP commands and return error codes """
    time.sleep(1)
    RUNTIME_LOG.debug('> {message}'.format(message=smtp_cmd))
    try:
        tcp_socket.sendall('{message}\r\n'.format(message=smtp_cmd))
    except IOError, errno:
        if errno == 32:
            RUNTIME_LOG.error('TCP socket closed by remote peer')
        else:
            RUNTIME_LOG.error('TCP socket error - see packet capture')
        return 1

    time.sleep(1)
    log_reply(tcp_socket)
    return 0

def log_reply(tcp_socket):
    """ Log text SMTP responses and errors """
    time.sleep(1)
    # This should return the SMTP server response 220
    #  Ex. "220 smtp.example.com ESMTP Postfix (smtp)"
    try:
        tcp_recv = tcp_socket.recv(4096)
        RUNTIME_LOG.debug('> {message}'.format(message=tcp_recv.strip()))
    except RuntimeError, errorcode:
        RUNTIME_LOG.error('TCP socket receive error {code}'.format(code=errorcode))

    if not re.compile(r'^2').match(tcp_recv):
        RUNTIME_LOG.error('SMTP server responded with error code')

def do_pcap():
    """ Install tcpdump RPM and start two packet captures """
    subprocess.call(["/etc/gss_support/install.sh"])

    pcap_dict = {}

    pcap_log = open('{path}/{file}{unique}.txt'.format(path=DIRPATH, file=TEMPLATE, unique=DATETIME), 'wb')
    pcap_dict['log'] = pcap_log
    pcap_dict['pcap1'] = subprocess.Popen(['tcpdump',
                                           '-anUlpvvs0',
                                           'tcp port {p}'.format(p=SMTPPORT)],
                                          stdout=pcap_log)

    pcap_bin = '{file}{unique}.pcap'.format(file=TEMPLATE, unique=DATETIME)
    pcap_dict['pcap2'] = subprocess.Popen(['tcpdump',
                                           '-anUlps0',
                                           '-w{file}'.format(file=pcap_bin),
                                           'tcp port {p}'.format(p=SMTPPORT)],
                                          cwd=DIRPATH,
                                          close_fds=True,
                                          bufsize=-1)

    time.sleep(5)

    return pcap_dict

def undo_pcap(pcap_dict):
    """ Terminate packet captures and uninstall tcpdump RPM """
    # TODO: for PROC in $(ps -ef | grep tcpdump | grep -v grep | awk '{print $2}'); do kill $PROC; done
    pcap_dict['pcap1'].terminate()
    pcap_dict['pcap2'].terminate()
    pcap_dict['pcap2'].wait()
    pcap_dict['log'].flush()
    pcap_dict['log'].close()
    pcap_dict['pcap1'].kill()
    pcap_dict['pcap1'].kill()
    subprocess.call(["/etc/gss_support/uninstall.sh"])

if __name__ == '__main__':
    if sys.argv[1:]:
        SMTPHOST = sys.argv[1]   # This can be IP or DNS
    else:
        print '\nUsage: {file} <IP|DNS>\n'.format(file=__file__)
        sys.exit(1)

    SMTPPORT = 25   # SMTP TCP port - SSL/TLS not supported
    TIMEOUT = 300   # TCP connection timeout - RFC 2821 spec
    DIRPATH = '/c3'
    TEMPLATE = 'smtp-cnxn'
    DATETIME = time.strftime("-%Y%m%d-%H%M%S")

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
