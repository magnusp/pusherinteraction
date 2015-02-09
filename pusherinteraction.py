import sys
import os
import json
import Queue
import hashlib
import hmac

from twisted.conch.telnet import TelnetProtocol
from twisted.internet.protocol import ServerFactory
from twisted.application.internet import TCPServer

from autobahn.twisted.websocket import WebSocketClientProtocol, WebSocketClientFactory


class PrivateSubscribeEvent:
    def __init__(self, socket_id, channel_name):
        self.channel_name = channel_name
        self.signature = hmac.new(PUSHER_SECRET, msg="%s:private-%s" % (socket_id, channel_name),
                                  digestmod=hashlib.sha256).hexdigest()

    def marshall(self):
        return json.dumps({
            "event": "pusher:subscribe",
            "data": {
                "channel": "private-%s" % self.channel_name,
                "auth": "%s:%s" % (PUSHER_KEY, self.signature)
            }
        })


class PrivatePublishEvent:
    def __init__(self, event, channel_name, payload):
        self.event = event
        self.channel_name = channel_name
        self.payload = payload

    def marshall(self):
        return json.dumps({
            "event": "client-%s" % self.event,
            "channel": "private-%s" % self.channel_name,
            "data": self.payload
        })


class TelnetEcho(TelnetProtocol):
    def enableRemote(self, option):
        self.transport.write("You tried to enable %r (I rejected it)\r\n" % (option,))
        return False


    def disableRemote(self, option):
        self.transport.write("You disabled %r\r\n" % (option,))


    def enableLocal(self, option):
        self.transport.write("You tried to make me enable %r (I rejected it)\r\n" % (option,))
        return False


    def disableLocal(self, option):
        self.transport.write("You asked me to disable %r\r\n" % (option,))


    def dataReceived(self, data):
        self.transport.write("I received %r from you\r\n" % (data,))
        self.factory.queue.put(data, False)


class MQTelnetFactory(ServerFactory):
    def __init__(self, queue):
        self.queue = queue


class MyClientProtocol(WebSocketClientProtocol):
    q = None
    subscribed = False
    socket_id = None
    subscriptions = []

    def onConnect(self, response):
        self.socket_id = None
        print("Server connected: {0}".format(response.peer))

    def onOpen(self):
        print("WebSocket connection open.")

        def flush_queue():
            try:
                msg = self.factory.queue.get(block=False).rstrip()
                if msg == 'sub' and not self.subscribed:
                    self.sendMessage((PrivateSubscribeEvent(self.socket_id, 'pusherinteraction')).marshall())
                if msg == 'pub' and len(self.subscriptions) > 0:
                    self.sendMessage((PrivatePublishEvent('telnet', 'pusherinteraction', 'Static payload from telnet client!')).marshall())
                if msg == 'disco':
                    self.transport.loseConnection()

            except Queue.Empty:
                pass
            self.factory.reactor.callLater(0, flush_queue)

        flush_queue()

    def onMessage(self, payload, isBinary):
        if isBinary:
            print("Binary message received: {0} bytes".format(len(payload)))
        else:
            decoded_payload = payload.decode('utf8')
            print("Text message received: {0}".format(decoded_payload))
            try:
                pusher_struct = json.loads(decoded_payload)
                if pusher_struct.has_key("event"):
                    self.process_pusher_event(pusher_struct)
            except Exception as e:
                pass

    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))

    def process_pusher_event(self, event):
        eventname = event[u'event']
        try:
            data = json.loads(event[u'data'])
        except ValueError as e:
            data = event[u'data']

        if eventname == u'pusher:connection_established':
            self.socket_id = data[u'socket_id']
        if eventname == u'pusher_internal:subscription_succeeded':
            self.subscriptions.append(event[u'channel'])
        pass


class MQWebSocketClientFactory(WebSocketClientFactory):
    def __init__(self, queue, *args, **kwargs):
        self.queue = queue
        WebSocketClientFactory.__init__(self, *args, **kwargs)


if __name__ == '__main__':
    PUSHER_KEY = os.getenv('PUSHER_KEY', None)
    PUSHER_SECRET = os.getenv('PUSHER_SECRET', None)
    PUSHER_APPID = os.getenv('PUSHER_APPID', None)

    from twisted.python import log
    from twisted.internet import reactor

    log.startLogging(sys.stdout)

    shared_queue = Queue.Queue(10)

    pusher_url = "ws://ws.pusherapp.com/app/{0}?client={1}&version={2}&protocol={3}".format(
        PUSHER_KEY,
        'pusherinteraction',
        '1.0',
        7
    )

    wsfactory = MQWebSocketClientFactory(shared_queue, pusher_url, debug=True)
    wsfactory.protocol = MyClientProtocol

    telnetfactory = MQTelnetFactory(shared_queue)
    telnetfactory.protocol = TelnetEcho

    reactor.connectTCP("ws.pusherapp.com", 80, wsfactory)
    reactor.listenTCP(port=8023, factory=telnetfactory)
    reactor.run()