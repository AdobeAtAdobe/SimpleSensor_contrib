"""
EventManager

Controls and handles events and figures out 
if the event needs to be handled and put in 
the list of registered clients.
"""
from simplesensor.shared import Message, ThreadsafeLogger
from .registry import BtleClient
from datetime import datetime
from threading import Thread
import time

_UPDATE_TOPIC = 'btle_update_nearby'
_CLIENT_IN_TOPIC = 'client_in'
_CLIENT_OUT_TOPIC = 'client_out'

class EventManager(object):
    def __init__(self, moduleConfig, pOutBoundQueue, clientRegistry, loggingQueue):
        self.loggingQueue = loggingQueue
        self.logger = ThreadsafeLogger(loggingQueue, __name__)

        self.__stats_totalRemoveEvents = 0
        self.__stats_totalNewEvents = 0
        self.clientRegistry = clientRegistry
        self.clientRegistry.onClientAdded += self.clientRegistered
        self.clientRegistry.onClientRemoved += self.clientRemoved
        self.moduleConfig = moduleConfig
        self.outBoundEventQueue = pOutBoundQueue
        self.alive = True

        self._sendClientInMessages = self.moduleConfig['SendClientInMessages']
        self._sendClientOutMessages = self.moduleConfig['SendClientOutMessages']
        self._sendUpdateMessages = self.moduleConfig['SendUpdateMessages']

        if self._sendUpdateMessages:
            self._updateFPS = self.moduleConfig['UpdateFPS']
            self.updateLoopThread = Thread(target=self.updateLoop)
            self.updateLoopThread.start()

    def updateLoop(self):
        """
        updateLoop
        Sends an update message on a set frequency.
        """
        while(self.alive):
            self.sendEventToController(topic=_UPDATE_TOPIC)
            time.sleep(1/self._updateFPS)

    def registerDetectedClient(self, detectedData):
        #self.logger.debug("Registering detected client %s"%
        #   detectedData.extraData["beaconMac"])
        eClient = self.clientRegistry.getClient(
            detectedData.extraData["beaconMac"])

        #check for existing
        if eClient == None:
            #Newly found client
            if self.moduleConfig['InterfaceType'] == 'btle':
                rClient = BtleClient(
                    detectedData,
                    self.moduleConfig,
                    self.loggingQueue)
            #self.logger.debug("New client with MAC %s found."%
            #   detectedData.extraData["beaconMac"])

            if rClient.shouldSendClientInEvent():
                self.sendEventToController(topic=_CLIENT_IN_TOPIC, client=rClient)
            elif rClient.shouldSendClientOutEvent():
                #if self.moduleConfig['EventManagerDebug']:
                    #self.logger.debug("######################" +
                    #   "SENDING CLIENT OUT eClient ######################")
                self.sendEventToController(topic=_CLIENT_OUT_TOPIC, client=rClient)

            self.clientRegistry.addClient(rClient)

        else:
            eClient.updateWithNewDetectedClientData(detectedData)
            if eClient.shouldSendClientInEvent():
                #if self.moduleConfig['EventManagerDebug']:
                    #self.logger.debug###################### "+
                    #   "SENDING CLIENT IN ######################")
                self.sendEventToController(topic=_CLIENT_IN_TOPIC, client=eClient)
            elif eClient.shouldSendClientOutEvent():
                #if self.moduleConfig['EventManagerDebug']:
                    #self.logger.debug###################### "
                    #   +"SENDING CLIENT OUT rClient ######################")
                self.sendEventToController(topic=_CLIENT_OUT_TOPIC, client=eClient)

            self.clientRegistry.updateClient(eClient)

    def registerClients(self,detectedDatas):
        for detectedData in detectedDatas:
            self.registerDetectedClient(detectedData)

    def getEventAuditData(self):
        """Returns a dict with the total New and Remove events the engine has seen since startup"""
        return {
            'NewEvents': self.__stats_totalNewEvents, 
            'RemoveEvents': self.__stats_totalRemoveEvents
            }

    def clientRegistered(self, sender, client):
        #if self.moduleConfig['EventManagerDebug']:
            #self.logger.debug("######### NEW CLIENT REGISTERED " +
            #   "%s #########"%client.detectedData.extraData["beaconMac"])

        #we dont need to count for ever and eat up all the memory
        if self.__stats_totalNewEvents > 1000000:
            self.__stats_totalNewEvents = 0
        else:
            self.__stats_totalNewEvents += 1

    def clientRemoved(self, sender, client):
        #if self.moduleConfig['EventManagerDebug']:
            #self.logger.debug("######### REGISTERED REMOVED "+
            #   "%s #########"%client.detectedData.extraData["beaconMac"])

        if client.sweepShouldSendClientOutEvent():
            self.sendEventToController(topic=_CLIENT_OUT_TOPIC, client=client)

        #we dont need to count for ever and eat up all the memory
        if self.__stats_totalRemoveEvents > 1000000:
            self.__stats_totalRemoveEvents = 0
        else:
            self.__stats_totalRemoveEvents  += 1

    def sendEventToController(self, topic, client=None):

        # TODO:// review this. i think we could clean a bunch with a standard 
            # in topic like /module_name/mode if defined mode for example btle has 
            # like 3 modes where the events are fired but their meaning is slighly 
            # different then you listen to a topic all events from that sensor are 
            # on that topic 
            #
            # the way is is now with topic being the event name I could see clientIn 
            # and clientOut from different modules and need to read the extra data 
            # to know if i care or not
            #
            # maybe that is right but we would need to define a high level spec so 
            # its not a mess.  Like topic /presence/event or /enviroment/data or 
            # something like that.
            #
            #topic="btle_beacon-%s"%(self.moduleConfig['GatewayType']),
            #sender_id=self.moduleConfig['CollectionPointId'],
            #sender_type=eventType,
        # immediately check if the event should be sent
        if ((topic==_CLIENT_IN_TOPIC and not self._sendClientInMessages) or
            (topic==_CLIENT_OUT_TOPIC and not self._sendClientOutMessages) or
            (topic==_UPDATE_TOPIC and not self._sendUpdateMessages)):
                return

        data = {}
        if client:
            data = client.getExtendedDataForEvent()  
        else:
            data = self.clientRegistry.getUpdateData()
            if len(data['nearby']) == 0: return

        eventMessage = Message(
            topic=topic,
            sender_id=self.moduleConfig['CollectionPointId'],
            sender_type=self.moduleConfig['GatewayType'],
            extended_data=data,
            timestamp=client.lastRegisteredTime if client else datetime.now())

        if topic == _CLIENT_IN_TOPIC:
            client.setClientInMessageSentToController()
        elif topic == _CLIENT_OUT_TOPIC:
            client.setClientOutMessageSentToController()
        elif topic == _UPDATE_TOPIC:
            # skip the updateClient call
            self.outBoundEventQueue.put(eventMessage)
            return

        # Update registry
        self.clientRegistry.updateClient(client)

        self.outBoundEventQueue.put(eventMessage)

    def stop(self):
        self.alive = False


