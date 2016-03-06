import queue
import re
import socket
import threading
import time

import pyglet


# http://eli.thegreenplace.net/2011/05/18/code-sample-socket-client-thread-in-python/
# http://tmi.twitch.tv/group/user/username/chatters

class TReciver(threading.Thread):
    def __init__(self, inQueue, con):
        """
        :type self :TReciver
        :type inQueue: queue.Queue
        :type con: Connection

        """
        threading.Thread.__init__(self)
        self.sock = None
        self.inQueue = inQueue
        self.stop_event = threading.Event()
        self.con = con

    def run(self):
        data = bytes()
        while not self.stop_event.is_set():
            # block until data is recived
            data += self.sock.recv(2048)
            # Check if connection is closed
            if len(data) == 0:
                break
            if len(data) > 1:
                split = data.split(b'\r\n')
                for msg in split[0:-1]:
                    self.inQueue.put(msg)
                if data[-2:] == b"\r\n":
                    data = bytes()
                else:
                    data = split[-1]

        # Notify observer
        self.con.connection_closed_event.set()

    def setSocket(self, sock):
        self.sock = sock

    def join(self, timeout=None):
        self.stop_event.set()
        super().join(timeout)


class TSender(threading.Thread):
    def __init__(self, outQ, con):
        threading.Thread.__init__(self)
        self.outQueue = outQ
        self.socket = None
        self.stop_event = threading.Event()
        self.con = con
        ''':type:Connection'''

    def run(self):
        while not self.stop_event.is_set() or not self.con.connection_closed_event.is_set():
            try:
                self.socket.send(self.outQueue.get(block=True, timeout=1))
            except queue.Empty:
                pass

            # mods can send 100 messages in 30 seconds
            # 30 / 100 = 0,3
            time.sleep(0.3)

    def setSocket(self, socket):
        self.socket = socket

    def join(self, timeout=None):
        self.stop_event.set()
        super().join(timeout)


class Connection(object):
    def __init__(self):
        self.inQueue = queue.Queue()
        self.outQueue = queue.Queue()
        self.host = "irc.twitch.tv"
        self.port = 6667
        self.sock = None
        self.tReciver = TReciver(self.inQueue, self)
        self.tSender = TSender(self.outQueue, self)
        self.connection_closed_event = threading.Event()

    def connect(self, host=None, port=None):
        """
            Connect to an IRC service

        :param host: Host to connect to
        :type host: str
        :param port: Port the host listens on
        :type port: int

        """
        self.host = host or self.host
        self.port = port or self.port
        self.sock = socket.create_connection((self.host, self.port))
        self.tReciver.setSocket(self.sock)
        self.tSender.setSocket(self.sock)
        self.tReciver.start()
        self.tSender.start()

    def send(self, msg):
        """
            Sends the message in Unicode with \r\n at the end to the socket

        :param msg: Message to be send
        :type msg: str
        """
        if isinstance(msg, str):
            msg = msg.encode("utf-8")
        if len(msg) == 0:
            msg = b'\r\n'
        elif len(msg) == 1:
            if msg == b'\r' or msg == b'\n':
                msg = b'\r\n'
            else:
                msg += b'\r\n'
        elif len(msg) >= 2:
            if msg[-2:] != b'\r\n':
                msg += b'\r\n'

        self.outQueue.put(msg)

    def recive(self, blocking=True, timeout=1):
        return self.inQueue.get(block=blocking, timeout=timeout).decode("utf-8")

    def close(self):
        self.connection_closed_event.set()
        self.sock.close()
        self.tSender.join()
        self.tReciver.join()


class Message(object):
    def __init__(self, username, channel, message):
        """
            Message-Object is a container for messages from a channel

        :param username: The username of the user who send the message
        :type username: str
        :param channel: The channel the message is recived in
        :type channel: str
        :param message: The message, which is recived
        :type message:str
        """
        self.username = username
        self.channel = channel
        self.message = message

    def __str__(self):
        return "{} in {}:{}".format(self.username, self.channel, self.message)


class TwitchClient(threading.Thread, pyglet.event.EventDispatcher):
    def __init__(self, username, password, channel):
        pyglet.event.EventDispatcher.__init__(self)
        threading.Thread.__init__(self)

        self.password = password
        self.username = username
        self.con = Connection()
        self.channel = channel

        self.pat_message = re.compile(
            r":(?P<name>[^!]*)!(?P=name)@(?P=name).tmi.twitch.tv PRIVMSG (?P<channel>#[\S]*) :(?P<message>.*$)")
        self.pat_join = re.compile(
            r":(?P<name>[^!]*)!(?P=name)@(?P=name).tmi.twitch.tv JOIN (?P<channel>#[\S]*)")
        self.pat_leave = re.compile(
            r":(?P<name>[^!]*)!(?P=name)@(?P=name).tmi.twitch.tv PART (?P<channel>#[\S]*)")

    def connect(self):
        self.con.connect()
        # login
        self.send_raw("PASS {}".format(self.password))
        self.send_raw("NICK {}".format(self.username))
        # request channel events
        # https://github.com/justintv/Twitch-API/blob/master/IRC.md#membership
        self.send_raw("CAP REQ :twitch.tv/membership")
        # join channel
        self.send_raw("JOIN {}".format(self.channel))

        while not self.con.connection_closed_event.is_set():
            try:
                msg = self.con.recive()
                print(msg)
                if msg == "PING :tmi.twitch.tv":
                    self.con.send("PONG :tmi.twitch.tv")
                else:
                    match = self.pat_message.match(msg)
                    if match is not None:
                        r = Message(match.group('name'),
                                    match.group('channel'),
                                    match.group('message'))
                        self.dispatch_msg(r)
                    match = None
                    match = self.pat_join.match(msg)
                    if match is not None:
                        self.dispatch_join(username=match.group('name'), channel=match.group('channel'))
            except queue.Empty:
                pass

    def run(self):
        self.connect()

    def send_raw(self, msg):
        self.con.send(msg)

    def send_chat(self, msg):
        self.send_raw("PRIVMSG {} :{}".format(self.channel, msg))

    def dispatch_msg(self, msg):
        self.dispatch_event('on_message', self, msg)

    def join(self, timeout=None):
        super().join(timeout)

    def dispatch_join(self, username, channel):
        self.dispatch_event('on_join', self, channel, username)
