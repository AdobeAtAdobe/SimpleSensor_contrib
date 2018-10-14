import time
import json
import requests
import platform
from threading import Thread
# from multiprocessing import Process
from . import BluegigaDevice
from .. import DetectionData
from simplesensor.shared import ThreadsafeLogger

# required callback keys
_ON_SCAN = 'onScan'

class DeviceThread(Thread):
    """
    Controller thread, manage the instance of BluegigaDevice.
    """
    def __init__(self, callbacks, btleConfig, loggingQueue, debugMode=False):
        super().__init__()
        # Logger
        self.loggingQueue = loggingQueue
        self.logger = ThreadsafeLogger(loggingQueue, __name__)
        self.alive = True
        self.callbacks = self.sanitizeCallbacks(callbacks)
        self.btleConfig = btleConfig
        # self.queue = queue
        self.device = BluegigaDevice(
            self.scanCallback,
            self.btleConfig,
            self.loggingQueue)

    def run(self):
        """
        Main thread entry point.
        Repeatedly call scan() method on
        device controller BluegigaDevice.

        Send results or failures back to main
        thread via callbacks.
        """
        try:
            self.device.start()
        except Exception as e:
            self.logger.error("Unable to connect to BTLE device: %s"%e)
            self.sendFailureNotice("Unable to connect to BTLE device")
            self.stop()

        while self.alive:
            # try:
            self.device.scan()
            # except Exception as e:
            #     self.logger.error("Unable to scan BTLE device: %s"%e)
            #     self.sendFailureNotice("Unable to connect to BTLE device to perform a scan")
            #     self.stop()

            # don't burden the CPU
            time.sleep(0.01)

    def scanCallback(self,sender,args):
        """
        Callback for the scan event on the device controller.
        Prints the event in a formatted way for tuning purposes.
        """
        #check to make sure there is enough data to be a beacon
        if len(args["data"]) > 15:
            try:
                majorNumber = args["data"][26] | (args["data"][25] << 8)
                # self.logger.debug("majorNumber=%i"%majorNumber)
            except:
                majorNumber = 0
            try:
                minorNumber = args["data"][28] | (args["data"][27] << 8)
                # self.logger.debug("minorNumber=%i"%minorNumber)
            except:
                minorNumber = 0

            if (self.btleConfig['BtleAdvertisingMajorMin'] <= majorNumber <= self.btleConfig['BtleAdvertisingMajorMax']) and (self.btleConfig['BtleAdvertisingMinorMin'] <= minorNumber <= self.btleConfig['BtleAdvertisingMinorMax']):
                udid = "%s" % ''.join(['%02X' % b for b in args["data"][9:25]])
                rssi = args["rssi"]
                beaconMac = "%s" % ''.join(['%02X' % b for b in args["sender"][::-1]])
                rawTxPower = args["data"][29]

                if rawTxPower <= 127:
                    txPower = rawTxPower
                else:
                    txPower = rawTxPower - 256

                if self.btleConfig['BtleTestMode']:
                    self.logger.debug("=============================== eventScanResponse START ===============================")
                    #self.logger.debug("self.btleConfig['BtleAdvertisingMinor'] == %i and self.btleConfig['BtleAdvertisingMinor'] == %i "%(majorNumber,minorNumber))
                    #self.logger.debug("yep, we care about this major and minor so lets create a detected client and pass it to the event manager")
                    self.logger.debug("Major=%s"%majorNumber)
                    self.logger.debug("Minor=%s"%minorNumber)
                    self.logger.debug("UDID=%s"%udid)
                    self.logger.debug("rssi=%s"%rssi)
                    self.logger.debug("beaconMac=%s"%beaconMac)
                    self.logger.debug("txPower=%i"%txPower)
                    self.logger.debug("rawTxPower=%i"%rawTxPower)
                    self.logger.debug("================================= eventScanResponse END =================================")

                #package it up for sending to the queue
                detectionData = DetectionData(
                    'btle',
                    udid=udid,
                    beaconMac=beaconMac,
                    majorNumber=majorNumber,
                    minorNumber=minorNumber,
                    tx=txPower,
                    rssi=rssi)
                
                #put it on the queue for the event manager to pick up
                self.callbacks[_ON_SCAN](detectionData)

    def sanitizeCallbacks(self, cbs):
        """
        Make sure required callbacks are included and callable.
        Return only the required callbacks.
        """
        assert(callable(cbs[_ON_SCAN]))
        if len(cbs) > 1:
            return [cbs[_ON_SCAN]]
        return cbs

    def stop(self):
        self.alive = False

    def sendFailureNotice(self, msg):
        if len(self.btleConfig['SlackChannelWebhookUrl']) > 10:
            myMsg = ("Help, I've fallen and can't get up! "+
                "\n %s. \nSent from %s"%(msg,platform.node()))
            payload = {'text': myMsg}
            r = requests.post(
                self.btleConfig['SlackChannelWebhookUrl'], 
                data = json.dumps(payload))