import socket

from poller import globalPoller, POLL_EVENT_TYPE
from tcp_connection import TcpConnection

class SERVER_STATE:
    UNBINDED = 0,
    BINDED = 1

class TcpServer(object):

    def __init__(self, host, port, onNewConnection,
                 sendBufferSize = 2 ** 13,
                 recvBufferSize = 2 ** 13,
                 connectionTimeout = 3.5):
        self.__host = host
        self.__port = int(port)
        self.__sendBufferSize = sendBufferSize
        self.__recvBufferSize = recvBufferSize
        self.__socket = None
        self.__fileno = None
        self.__state = SERVER_STATE.UNBINDED
        self.__onNewConnectionCallback = onNewConnection
        self.__connectionTimeout = connectionTimeout

    def bind(self):
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.__sendBufferSize)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.__recvBufferSize)
        self.__socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__socket.setblocking(0)
        self.__socket.bind((self.__host, self.__port))
        self.__socket.listen(5)
        self.__fileno = self.__socket.fileno()
        globalPoller().subscribe(self.__fileno,
                                self.__onNewConnection,
                                POLL_EVENT_TYPE.READ | POLL_EVENT_TYPE.ERROR)
        self.__state = SERVER_STATE.BINDED

    def unbind(self):
        self.__state = SERVER_STATE.UNBINDED
        if self.__fileno is not None:
            globalPoller().unsubscribe(self.__fileno)
            self.__fileno = None
        if self.__socket is not None:
            self.__socket.close()

    def __onNewConnection(self, descr, event):
        if event & POLL_EVENT_TYPE.READ:
            try:
                sock, addr = self.__socket.accept()
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.__sendBufferSize)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.__recvBufferSize)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.setblocking(0)
                conn = TcpConnection(socket=sock,
                                     timeout=self.__connectionTimeout,
                                     sendBufferSize=self.__sendBufferSize,
                                     recvBufferSize=self.__recvBufferSize)
                self.__onNewConnectionCallback(conn)
            except socket.error as e:
                if e.errno != socket.errno.EAGAIN:
                    self.unbind()
                    return

        if event & POLL_EVENT_TYPE.ERROR:
            self.unbind()
            return
