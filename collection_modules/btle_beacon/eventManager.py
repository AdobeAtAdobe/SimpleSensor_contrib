"""

"""
import os.path
import logging 
from simplesensor.shared import Message, ThreadsafeLogger
from .btleRegisteredClient import BtleRegisteredClient

class EventManager(object):
    def __init__(self, collectionPointConfig, pOutBoundQueue, registeredClientRegistry, loggingQueue):
        self.loggingQueue = loggingQueue
        self.logger = ThreadsafeLogger(loggingQueue, __name__)

        self.__stats_totalRemoveEvents = 0
        self.__stats_totalNewEvents = 0
        self.registeredClientRegistry = registeredClientRegistry
        self.registeredClientRegistry.eventRegisteredClientAdded += self.newClientRegistered
        self.registeredClientRegistry.eventRegisteredClientRemoved += self.removedRegisteredClient
        self.collectionPointConfig = collectionPointConfig
        self.outBoundEventQueue = pOutBoundQueue


    def registerDetectedClient(self, detectedClient):
        self.logger.debug("Registering detected client %s"%detectedClient.extraData["beaconMac"])
        eClient = self.registeredClientRegistry.getRegisteredClient(detectedClient.extraData["beaconMac"])

        #check for existing
        if eClient == None:
            #Newly found client
            if self.collectionPointConfig['InterfaceType'] == 'btle':
                rClient = BtleRegisteredClient(detectedClient,self.collectionPointConfig,self.loggingQueue)
            self.logger.debug("New client with MAC %s found."%detectedClient.extraData["beaconMac"])

            if rClient.shouldSendClientInEvent():
                self.sendEventToController(rClient, "clientIn")
            elif rClient.shouldSendClientOutEvent():
                self.logger.debug("########################################## SENDING CLIENT OUT eClient ##########################################")
                self.sendEventToController(rClient, "clientOut")

            self.registeredClientRegistry.addNewRegisteredClient(rClient)

        else:
            eClient.updateWithNewDetectedClientData(detectedClient)
            if eClient.shouldSendClientInEvent():
                #self.logger.debug("########################################## SENDING CLIENT IN ##########################################")
                self.sendEventToController(eClient,"clientIn")
            elif eClient.shouldSendClientOutEvent():
                self.logger.debug("########################################## SENDING CLIENT OUT rClient ##########################################")
                self.sendEventToController(eClient,"clientOut")

            self.registeredClientRegistry.updateRegisteredClient(eClient)

    def registerClients(self,detectedClients):
        for detectedClient in detectedClients:
            self.registerDetectedClient(detectedClient)

    def getEventAuditData(self):
        """Returns a dict with the total New and Remove events the engine has seen since startup"""
        return {'NewEvents': self.__stats_totalNewEvents, 'RemoveEvents': self.__stats_totalRemoveEvents}

    def newClientRegistered(self,sender,registeredClient):
        self.logger.debug("######### NEW CLIENT REGISTERED %s #########"%registeredClient.detectedClient.extraData["beaconMac"])

        #we dont need to count for ever and eat up all the memory
        if self.__stats_totalNewEvents > 1000000:
            self.__stats_totalNewEvents = 0
        else:
            self.__stats_totalNewEvents += 1

    def removedRegisteredClient(self,sender,registeredClient):
        self.logger.debug("######### REGISTERED REMOVED %s #########"%registeredClient.detectedClient.extraData["beaconMac"])
        if registeredClient.sweepShouldSendClientOutEvent():
            self.sendEventToController(registeredClient,"clientOut")

        #we dont need to count for ever and eat up all the memory
        if self.__stats_totalRemoveEvents > 1000000:
            self.__stats_totalRemoveEvents = 0
        else:
            self.__stats_totalRemoveEvents  += 1

    def sendEventToController(self,registeredClient,eventType):

        eventMessage = Message(
            topic=eventType,
            sender_id=self.collectionPointConfig['CollectionPointId'],
            sender_type=self.collectionPointConfig['GatewayType'],
            extended_data=registeredClient.getExtendedDataForEvent(),
            timestamp=registeredClient.lastRegisteredTime)

        if eventType == 'clientIn':
            registeredClient.setClientInMessageSentToController()
        elif eventType == 'clientOut':
            registeredClient.setClientOutMessageSentToController()

        #update reg
        self.registeredClientRegistry.updateRegisteredClient(registeredClient)

        self.outBoundEventQueue.put(eventMessage)


