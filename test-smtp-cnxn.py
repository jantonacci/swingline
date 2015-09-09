#!/usr/bin/python
import socket, sys, time, re, subprocess, logging

def main():

    pcapProc = doTcpdump()

    RUNTIME_LOG.info('SMTP service check for {h}:{p} (timeout={t}s)'.format(h='localhost', p=SMTPPORT, t=TIMEOUT))
    clientSocket = socket.create_connection(('localhost', SMTPPORT), TIMEOUT)
    clientSocket.settimeout(300)
    printRecv(clientSocket)
    doSmtp(clientSocket)
    clientSocket.close()

    RUNTIME_LOG.info('SMTP service check for {h}:{p} (timeout={t}s)'.format(h=SMTPHOST, p=SMTPPORT, t=TIMEOUT))
    clientSocket = socket.create_connection((SMTPHOST, SMTPPORT), TIMEOUT)
    clientSocket.settimeout(300)
    printRecv(clientSocket)
    doSmtp(clientSocket)
    clientSocket.close()

    unDoTcpdump(pcapProc)

    sys.exit(0)

def doTcpdump():
    subprocess.call(["/etc/gss_support/install.sh"])

    pcapProc = {}

    tcpdumpLog = open('{path}/{file}{unique}.txt'.format(path=DIRPATH, file=TEMPLATE, unique=DATETIME), 'wb')
    pcapProc['file1'] = tcpdumpLog
    pcapProc['pcap1'] = subprocess.Popen(['tcpdump',
                                          '-anUlpvvs0',
                                          'tcp port {p}'.format(p=SMTPPORT)],
                                         stdout=tcpdumpLog)

    tcpdumpCap = '{file}{unique}.pcap'.format(file=TEMPLATE, unique=DATETIME)
    pcapProc['file2'] = tcpdumpCap
    pcapProc['pcap2'] = subprocess.Popen(['tcpdump',
                                          '-anUlps0',
                                          '-w{file}'.format(file=tcpdumpCap),
                                          'tcp port {p}'.format(p=SMTPPORT)],
                                         cwd='/c3',
                                         close_fds=True,
                                         bufsize=-1)

    time.sleep(5)

    return pcapProc

def unDoTcpdump(pcapProc):
    pcapProc['pcap1'].terminate()
    pcapProc['pcap2'].terminate()
    pcapProc['pcap2'].wait()
    pcapProc['file1'].flush()
    pcapProc['file1'].close()
    pcapProc['pcap1'].kill()
    pcapProc['pcap1'].kill()
    subprocess.call(["/etc/gss_support/uninstall.sh"])

def printRecv(clientSocket):
    time.sleep(1)
    # This should return the SMTP server response 220
    #  Ex. "220 smtp.example.com ESMTP Postfix (smtp)"
    try:
        serverRead = clientSocket.recv(4096)
    except RuntimeError:
        RUNTIME_LOG.error('SMTP server response error')
        exit
    RUNTIME_LOG.debug('< {message}'.format(message=serverRead)),
    if not re.compile(r'^2').match(serverRead):
        RUNTIME_LOG.error('SMTP server responded with error code')

def doSmtp(clientSocket):
    doSmtpVerbs(clientSocket, 'EHLO {name}'.format(name=socket.getfqdn()))
    doSmtpVerbs(clientSocket, 'RSET')
    doSmtpVerbs(clientSocket, 'HELO {name}'.format(name=socket.getfqdn()))
    doSmtpVerbs(clientSocket, 'NOOP')
    doSmtpVerbs(clientSocket, 'QUIT')

def doSmtpVerbs(clientSocket, smtpVerb):
    time.sleep(1)
    RUNTIME_LOG.debug('> {message}'.format(message=smtpVerb))
    clientSocket.sendall('{message}\r\n'.format(message=smtpVerb))
    time.sleep(1)
    printRecv(clientSocket)

if __name__ == '__main__':
    if sys.argv[1:]:
        SMTPHOST = sys.argv[1]   # This can be IP or DNS
    else:
        print('Usage: test-smtp-cnxn.py <IP|DNS>')
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
    LOGFILE = logging.FileHandler('{path}/{file}{unique}.log'.format(path='/c3', file=TEMPLATE, unique=DATETIME))
    LOGFILE.setFormatter(FMT_LOG_DEFAULT)
    RUNTIME_LOG.addHandler(CONSOLE)
    RUNTIME_LOG.addHandler(LOGFILE)
    RUNTIME_LOG.setLevel(logging.DEBUG)


    main()

#EOF
