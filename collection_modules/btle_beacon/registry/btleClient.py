"""
BtleClient
"""

from simplesensor.shared import ThreadsafeLogger
# from ..devices import DetectionData
from .filter import Filter
from ..uidMap import UIDMap
import time
from datetime import datetime
import math
 
class BtleClient(object):
    def __init__(self, detectionData, collectionPointConfig, loggingQueue):
        self.loggingQueue = loggingQueue
        self.logger = ThreadsafeLogger(loggingQueue, "BtleRegisteredClient")
        
        # Counters and variables
        self.clientInRangeTrigerCount = 1
        self.prevClientInMsgTime = None
        self.prevClientOutMsgTime = None
        self.numClientInRange=0
        self.numClientOutRange=0
        self.timeInCollectionPointInMilliseconds = 0
        self.firstRegisteredTime = datetime.now()
        self.collectionPointConfig = collectionPointConfig
        self.filter = Filter(detectionData.extraData['rssi'])
        try:
            self.uidMap = UIDMap()
        except Exception as e:
            self.logger.warning('cant instantiate uid map: %s '%e)

        # Constants
        self._proximityEventInterval = self.collectionPointConfig['ProximityEventInterval']
        self._outClientThreshold = self.collectionPointConfig['BtleClientOutCountThreshold']

        self._gatewayType = self.collectionPointConfig['GatewayType']

        self._rssiClientInThresh = self.collectionPointConfig['BtleRssiClientInThreshold']
        self._rssiErrorVar = self.collectionPointConfig['BtleRssiErrorVariance']
        self.__clientOutThresholdMin = int(
            self._rssiClientInThresh + 
            (self._rssiClientInThresh * self._rssiErrorVar)
            )
        self._clientInThreshType = self.collectionPointConfig['BtleRssiClientInThresholdType']
        self._debugEventManager = self.collectionPointConfig['EventManagerDebug']

        # Initiate event when client is detected
        self.handleNewDetectedClientEvent(detectionData)

    def updateWithNewDetectedClientData(self, detectionData):
        """
        updateWithNewDetectedClientData
        part of interface for Registered Client
        """
        self.timeInCollectionPointInMilliseconds = (datetime.now() - self.firstRegisteredTime).total_seconds()*1000
        # standard shared methods when we see a detected client
        self.handleNewDetectedClientEvent(detectionData)

    # Common methods are handled here for updateWithNewDetectedClientData and init
    def handleNewDetectedClientEvent(self, detectionData):
        self.lastRegisteredTime = datetime.now()
        self.detectionData = detectionData
        self.txPower = detectionData.extraData['tx']
        self.beaconId = detectionData.extraData['udid']
        self.filter.update(self.detectionData.extraData['rssi'])
        self.incrementInternalClientEventCounts(detectionData)

    def incrementInternalClientEventCounts(self, detectionData):
        if self._gatewayType == 'proximity':
            if self._clientInThreshType == 'rssi':
                # Are they in or are they out of range 
                # Increment internal count, used to normalize events.
                if (self.detectionData.extraData['rssi'] >= self._rssiClientInThresh):
                    self.numClientInRange += 1
                    self.numClientOutRange = 0
                    self.logClientRange("CLIENTIN")
                elif (self.detectionData.extraData['rssi'] < self.__clientOutThresholdMin):
                    self.numClientOutRange += 1
                    #self.numClientInRange = 0
                    self.logClientRange("CLIENTOUT")

    #part of interface for Registered Client
    def shouldSendClientInEvent(self):
        # self.logger.debug("SHOULD SEND CLIENT IN? ")
        # self.logger.debug("self.prevClientInMsgTime: %s"%self.prevClientInMsgTime)
        # self.logger.debug("self.prevClientOutMsgTime: %s"%self.prevClientOutMsgTime)
        # if(self.prevClientOutMsgTime is not None and self.prevClientInMsgTime is not None):
        #     self.logger.debug("(self.prevClientOutMsgTime-self.prevClientInMsgTime).total_seconds(): %s"%(self.prevClientOutMsgTime-self.prevClientInMsgTime).total_seconds())
        # if(self.prevClientInMsgTime is not None):
        #     self.logger.debug("datetime.now() - self.prevClientInMsgTime).total_seconds()*1000: %s"%((datetime.now() - self.prevClientInMsgTime).total_seconds()*1000))
        # self.logger.debug("self.numClientInRange > self.clientInRangeTrigerCount: %s > %s"%(self.numClientInRange, self.clientInRangeTrigerCount))
        if self._gatewayType == 'proximity':
            if (self.prevClientInMsgTime == None or 
                (self.prevClientOutMsgTime != None and 
                    (self.prevClientOutMsgTime-self.prevClientInMsgTime).total_seconds() > 0) or
                (datetime.now() - self.prevClientInMsgTime).total_seconds()*1000 >= self._proximityEventInterval):
                    if self.numClientInRange > self.clientInRangeTrigerCount:
                        self.logClientEventSend(" ClientIN event sent to controller ")
                        self.zeroEventRangeCounters()
                        return True

        #TODO add in other types of gateway types
        # self.logger.debug("NOT SENDING CLIENT IN")
        return False

    #part of interface for Registered Client
    def shouldSendClientOutEvent(self):
        if self._gatewayType == 'proximity':
            #check the time to see if we need to send a message
            #have we ever sent an IN event? if not we dont need to send an out event
            if self.prevClientInMsgTime:
                #have we sent a client out since the last client in?  if so we dont need to throw another
                if (self.prevClientOutMsgTime == None or self.prevClientOutMsgTime < self.prevClientInMsgTime):
                    #do we have enought qualifying out events. we dont want to throw one too soon
                    if (self.numClientOutRange >= self._outClientThreshold):
                        self.logClientEventSend("ClientOUT event a sent to controller")
                        self.zeroEventRangeCounters()
                        return True

                #check timing on last event sent
                if (self.prevClientOutMsgTime is not None and
                    (datetime.now() - self.prevClientOutMsgTime).total_seconds()*1000 < self._proximityEventInterval):
                        return False
                elif self.prevClientOutMsgTime is not None:
                    self.logClientEventSend("ClientOUT event b sent to controller")
                    self.zeroEventRangeCounters()
                    return True
            elif self.numClientOutRange > self._outClientThreshold:
                # self.logger.debug("Client out count "+
                #    "%i is past max.  Resetting." %self.numClientOutRange)
                self.numClientOutRange = 0
                
        #TODO add in other types of gateway types
        return False

    #part of interface for Registered Client
    def sweepShouldSendClientOutEvent(self):
        if self._gatewayType == 'proximity':
            # has an in event been sent yet? if not, no sweep needed
            if self.prevClientInMsgTime:
                # sweep old clients, so check most recent message sent
                # if no message has been sent in the past proximityEventInterval*3 milliseconds
                # sweep the client because it is probably gone
                if (self.prevClientOutMsgTime is None or 
                    (self.prevClientInMsgTime>self.prevClientOutMsgTime and
                    (datetime.now() - self.prevClientOutMsgTime).total_seconds()*1000 > 
                        self._proximityEventInterval*3)):
                            self.logClientEventSend("Sweep case a is sending ClientOUT on")
                            self.zeroEventRangeCounters()
                            return True
                else:
                    return False
            else:
                return False
        #TODO add in other types of gateway types
        return False

    #part of interface for Registered Client
    def getMac(self):
        return self.detectionData.extraData["beaconMac"]

    def getTxPower(self):
        return self.txPower

    #zero out the BTLE event counters
    def zeroEventRangeCounters(self):
        self.numClientOutRange = 0
        self.numClientInRange = 0

    def logClientEventSend(self,message):
        if self._debugEventManager:
            self.logger.debug("")
            self.logger.debug("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
            self.logger.debug("%%%%%%%%%%%%%%%%%% %s %%%%%%%%%%%%%%%%%%" %message)
            self.logger.debug("    MAC is %s " %self.getMac())
            self.logger.debug("    Beacon ID is %s " %self.beaconId)
            self.logger.debug("    filtered RSSI %i" %self.filter.state)
            self.logger.debug("    RSSI %i" %self.detectionData.extraData['rssi'])
            self.logger.debug("    Major %i" %self.detectionData.extraData['majorNumber'])
            self.logger.debug("    Minor %i" %self.detectionData.extraData['minorNumber'])
            self.logger.debug("    BTLE RSSI client in threshold %i" %self.collectionPointConfig['BtleRssiClientInThreshold'])
            self.logger.debug("    BTLE RSSI client out threshold %i" %self.__clientOutThresholdMin)
            self.logger.debug("    inCount %i : outCount %i" %(self.numClientInRange,self.numClientOutRange))
            self.logger.debug("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
            self.logger.debug("")
        return


    def logClientRange(self,eventType):
        if self.collectionPointConfig['ShowClientRangeDebug']:

            if eventType.upper() == "CLIENTIN":
                self.logger.debug("<<<<<<<<<<<<<<<<< IN RANGE <<<<<<<<<<<<<<<<<")
            else:
                self.logger.debug(">>>>>>>>>>>>>>>>> OUT OF RANGE >>>>>>>>>>>>>>>>>")

            self.logger.debug("    MAC is %s " %self.getMac())
            self.logger.debug("    Beacon ID is %s " %self.beaconId)
            self.logger.debug("    RSSI %i" %self.detectionData.extraData['rssi'])
            self.logger.debug("    Major %i" %self.detectionData.extraData['majorNumber'])
            self.logger.debug("    Minor %i" %self.detectionData.extraData['minorNumber'])
            self.logger.debug("    BTLE RSSI client in threshold %i" %self.collectionPointConfig['BtleRssiClientInThreshold'])
            self.logger.debug("    BTLE RSSI client out threshold %i" %self.__clientOutThresholdMin)
            self.logger.debug("    inCount %i : outCount %i" %(self.numClientInRange,self.numClientOutRange))

            if eventType.upper() == "CLIENTIN":
                self.logger.debug("<<<<<<<<<<<<<<<<< IN RANGE END <<<<<<<<<<<<<<<<<")
            else:
                self.logger.debug(">>>>>>>>>>>>>>>>> OUT OF RANGE END >>>>>>>>>>>>>>>>>")

            self.logger.debug("")
        return

    #part of interface for Registered Client
    def getExtendedDataForEvent(self):
        extraData = {}
        extraData['gatewayType'] = self.collectionPointConfig['GatewayType']
        extraData['lastRegisteredTime'] = self.lastRegisteredTime if self.lastRegisteredTime==None else self.lastRegisteredTime.isoformat() 
        extraData['firstRegisteredTime'] = self.firstRegisteredTime if self.firstRegisteredTime==None else self.firstRegisteredTime.isoformat() 
        extraData['prevClientInMsgTime'] = self.prevClientInMsgTime if self.prevClientInMsgTime==None else self.prevClientInMsgTime.isoformat()
        extraData['prevClientOutMsgTime'] = self.prevClientOutMsgTime if self.prevClientOutMsgTime==None else self.prevClientOutMsgTime.isoformat()
        extraData['timeInCollectionPointInMilliseconds'] = self.timeInCollectionPointInMilliseconds
        extraData['rssi'] = self.detectionData.extraData['rssi']
        extraData['averageRssi'] = self.detectionData.extraData['rssi']
        extraData['filteredRssi'] = self.filter.state
        extraData['txPower'] = self.getTxPower()
        extraData['beaconId'] = self.beaconId
        extraData['beaconMac'] = self.detectionData.extraData["beaconMac"]
        extraData['major'] = self.detectionData.extraData["majorNumber"]
        extraData['minor'] = self.detectionData.extraData["minorNumber"]
        if self.collectionPointConfig['CecData']:
            extraData['industry'] = self.uidMap.get(self.beaconId)

        return extraData

    #part of interface for Registered Client
    def setClientInMessageSentToController(self):
        self.logger.debug('set client in message sent')
        self.prevClientInMsgTime = datetime.now()
        self.numClientInRange = 0

    #part of interface for Registered Client
    def setClientOutMessageSentToController(self):
        self.logger.debug('set client out message sent')
        self.prevClientOutMsgTime = datetime.now()
        self.numClientOutRange = 0
