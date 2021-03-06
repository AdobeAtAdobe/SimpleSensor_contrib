"""
WebsocketClientModule
Connects to websocket server host/port as defined in config.
Attempts reconnects on disconnection.
"""
from simplesensor.communication_modules.websocket_client import moduleConfigLoader as configLoader
from simplesensor.shared import ThreadsafeLogger, ModuleProcess, Message
from threading import Thread
import websocket
import time
import json




class WebsocketClientModule(ModuleProcess):

    def __init__(self, baseConfig, pInBoundEventQueue, pOutBoundEventQueue, loggingQueue):

        super(WebsocketClientModule, self).__init__()
        
        self.alive = True
        self.config = baseConfig
        self.inQueue = pInBoundEventQueue  # inQueue are messages from the main process to websocket clients
        self.outQueue = pOutBoundEventQueue  # outQueue are messages from clients to main process
        self.websocketClient = None
        self.loggingQueue = loggingQueue
        self.threadProcessQueue = None

        # Configs
        self.moduleConfig = configLoader.load(self.loggingQueue, __name__)

        # Constants
        self._port = self.moduleConfig['WebsocketPort']
        self._host = self.moduleConfig['WebsocketHost']

        # logging setup
        self.logger = ThreadsafeLogger(loggingQueue, __name__)

    def run(self):

        """ Main thread entry point.

        Sets up websocket server and event callbacks.
        Starts thread to monitor inbound message queue.
        """

        self.logger.info("Starting %s" % __name__)
        self.connect()

    def listen(self):
        self.threadProcessQueue = Thread(target=self.processQueue)
        self.threadProcessQueue.setDaemon(True)
        self.threadProcessQueue.start()

    def connect(self):
        #websocket.enableTrace(True)
        ws = websocket.WebSocketApp("ws://%s:%s"%(self._host, self._port),
        on_message = self.onMessage,
        on_error = self.onError,
        on_close = self.onClose)
        ws.on_open = self.onOpen
        ws.run_forever()

    def onError(self, ws, message):
        self.logger.error("Error callback fired, message: %s"%message)

    def onClose(self, ws):
        if self.alive:
            self.logger.warn("Closed")
            self.alive = False
            # TODO: reconnect timer
        else:
            self.logger.info("Closed")

    def onMessage(self, ws, message):
        self.logger.info("Message from websocket server: %s"%message)
        # Could put message on the out queue here to handle incoming coms

    def onOpen(self, ws):
        self.alive = True
        self.websocketClient = ws
        self.listen()

    def shutdown(self):
        """ Handle shutdown message. 
        Close and shutdown websocket server.
        Join queue processing thread.
        """

        self.logger.info("Shutting down %s"%__name__)

        try:
            self.logger.info("Closing websocket")
            self.websocketClient.close()
        except Exception as e:
            self.logger.error("Websocket close error : %s " %e)

        self.alive = False
        
        self.threadProcessQueue.join()

        time.sleep(1)
        self.exit = True

    def sendOutMessage(self, message):
        """ Send message to server """

        self.websocketClient.send(json.dumps(message.__dict__))

    def processQueue(self):
        """ Monitor queue of messages from main process to this thread. """

        while self.alive:
            if (self.inQueue.empty() == False):
                try:
                    message = self.inQueue.get(block=False,timeout=1)
                    if message is not None:
                        if (message.topic.upper()=="SHUTDOWN" and
                            message.sender_id.lower()=="main"):
                            self.logger.debug("SHUTDOWN handled")
                            self.shutdown()
                        else:
                            self.sendOutMessage(message)
                except Exception as e:
                    self.logger.error("Websocket unable to read queue : %s " %e)
            else:
                time.sleep(.25)
