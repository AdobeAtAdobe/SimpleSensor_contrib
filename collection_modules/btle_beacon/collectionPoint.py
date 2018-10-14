"""
BTLE iBeacon module
Main collection point
"""

from . import moduleConfigLoader as configLoader
from .devices.bluegiga import DeviceThread as BlueGigaDeviceThread
from .registry import ClientRegistry
from simplesensor.shared import ThreadsafeLogger, ModuleProcess
from .repeatedTimer import RepeatedTimer
from .eventManager import EventManager
from threading import Thread
from datetime import datetime
import multiprocessing as mp
import time

_ON_SCAN = 'onScan'

class BtleCollectionPoint(Thread):

    def __init__(self, baseConfig, pInBoundQueue, pOutBoundQueue, loggingQueue):
        """ Initialize new CamCollectionPoint instance.
        Setup queues, variables, configs, constants and loggers.
        """
        super().__init__()
        # super().__init__(baseConfig, pInBoundQueue, pOutBoundQueue, loggingQueue)
        self.loggingQueue = loggingQueue
        self.logger = ThreadsafeLogger(loggingQueue, __name__)

         # Queues
        self.outQueue = pOutBoundQueue # Messages from this thread to the main process
        self.inQueue = pInBoundQueue

        # Configs
        self.moduleConfig = configLoader.load(self.loggingQueue, __name__)
        self.config = baseConfig

        # Variables and objects
        self.alive = True
        self.callbacks = {
            _ON_SCAN: self.handleBtleClientEvent
        }
        self.clientRegistry = ClientRegistry(
            self.moduleConfig, 
            self.loggingQueue)

        self.eventManager = EventManager(
            self.moduleConfig, 
            pOutBoundQueue, 
            self.clientRegistry, 
            self.loggingQueue)

        # Threads
        self.btleThread = None
        self.repeatTimerSweepClients = None

        self.lastUpdate = datetime.now()

        # Constants
        self._cleanupInterval = self.moduleConfig['AbandonedClientCleanupInterval']

    def run(self):
        """
        Main thread entrypoint.
        Sets up and starts the DeviceThread.
        Loops repeatedly reading incoming messages.
        """
        # Pause for a bit to let things bootup on host machine
        self.logger.info("Pausing execution 15 seconds" +
            " waiting for other system services to start")
        time.sleep(15)
        self.logger.info("Done with our nap. " + 
            "Time to start looking for clients")

        # Start device thread, handles IO
        self.deviceThread = BlueGigaDeviceThread(
            self.callbacks, 
            self.moduleConfig, 
            self.loggingQueue)
        self.deviceThread.start()

        # Setup repeat task to run the sweep every X interval
        self.repeatTimerSweepClients = RepeatedTimer(
            (self._cleanupInterval/1000), 
            self.clientRegistry.sweepOldClients)

        self.logger.info("Starting to watch collection point inbound message queue")
        while self.alive:
            if not self.inQueue.empty():
                self.logger.info("Queue size is %s" % self.inQueue.qsize())
                try:
                    message = self.inQueue.get(block=False,timeout=1)
                    if message is not None:
                        if (message.topic=="SHUTDOWN" and message.sender_id=='main'):
                            self.logger.info("SHUTDOWN command handled on %s" % __name__)
                            self.shutdown()
                        else:
                            self.handleMessage(message)
                except Exception as e:
                    self.logger.error("Unable to read queue, error: %s " %e)
                    self.shutdown()
                self.logger.info("Queue size is %s after" % self.inQueue.qsize())
            else:
                time.sleep(.45)

    def handleBtleClientEvent(self, detectedClient):
        self.eventManager.registerDetectedClient(detectedClient)

    def handleMessage(self, msg):
        # Handle incoming messages, eg. from other collection points
        pass

    def killProcess(self, proc, timeout=1):
        """
        Kill a process, given a timeout to join.
        """
        self.logger.info('Joining process: %s'%proc)
        proc.join()
        p_sec = 0
        for second in range(timeout):
            if proc.is_alive():
                time.sleep(1)
                p_sec += 1
        if p_sec >= timeout:
            self.logger.info('Terminating process: %s'%proc)
            proc.terminate()

    def shutdown(self):
        self.logger.info("Shutting down")
        self.repeatTimerSweepClients.stop()
        self.eventManager.stop()
        self.deviceThread.stop()
        # self.killProcess(self.deviceThread)
        self.alive = False
        time.sleep(1)
        self.exit = True