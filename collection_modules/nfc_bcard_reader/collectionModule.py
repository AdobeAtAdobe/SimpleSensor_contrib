"""
Sample structure for a collection point module.
This module describes the basic uses of SimpleSensor.
To make your own module, this is a good place to start.
"""

from simplesensor.collection_modules.nfc_bcard_reader import moduleConfigLoader as configLoader
from simplesensor.shared import Message, ThreadsafeLogger, ModuleProcess
from multiprocessing import Process
from threading import Thread
import time 
import json
import struct
import math
import datetime
from smartcard.scard import *

class CollectionModule(ModuleProcess):

    # You can keep these parameters the same, all modules receive the same params
    # self - reference to self
    # baseConfig - configuration settings defined in /simplesensor/config/base.conf 
    #               (https://github.com/AdobeAtAdobe/SimpleSensor/blob/master/config/base.conf)
    # pInBoundQueue - messages from handler to this module
    # pOutBoundQueue - messages from this module to other modules
    # loggingQueue - logging messages for threadsafe logger

    def __init__(self, baseConfig, pInBoundQueue, pOutBoundQueue, loggingQueue):
        """ 
        Initialize new CollectionModule instance.
        """
        super(CollectionModule, self).__init__(baseConfig, pInBoundQueue, pOutBoundQueue, loggingQueue)

        # Most collection modules will follow a similar pattern...

        # 1. Set up some variables on the self object
        # Queues
        self.outQueue = pOutBoundQueue
        self.inQueue= pInBoundQueue
        self.loggingQueue = loggingQueue
        self.threadProcessQueue = None
        self.alive = False

        self.context = None
        self.reader = None

        # 2. Load the module's configuration file
        # Configs
        self.moduleConfig = configLoader.load(self.loggingQueue, __name__)
        self.config = baseConfig

        # 3. Set some constants to the self object from config parameters (if you want)
        self._id = self.moduleConfig['CollectionPointId']
        self._type = self.moduleConfig['CollectionPointType']
        self._port = self.moduleConfig['ReaderPortNumber']

        # 4. Create a threadsafe logger object
        self.logger = ThreadsafeLogger(loggingQueue, __name__)

    def run(self):
        """
        Main process method, run when the thread's start() function is called.
        Starts monitoring inbound messages to this module, and collection logic goes here.
        For example, you could put a loop with a small delay to keep polling the sensor, etc.
        When something is detected that's relevant, put a message on the outbound queue.
        """

        # Monitor inbound queue on own thread
        self.listen()
        self.alive = True

        while self.context == None:
            self.establish_context()

        while self.alive:
            while self.reader is None:
                print('.')
                self.reader = self.get_reader()
                if self.reader is None:
                    self.logger.info('Waiting for 5 seconds before '
                    + 'trying to find readers again. Is it plugged in?')
                    time.sleep(5)

            # connect to card
            card = self.get_card()
            if card is None or self.reader is None: 
                continue

            # try:
            cc_block_msg = [0xFF, 0xB0, 0x00, bytes([3])[0], 0x04]
            try:
                cc_block = self.send_transmission(card, cc_block_msg)
            except Exception as e:
                self.reader = None
                continue


            if (cc_block is None or cc_block[0] != 225): # magic number 0xE1 means data to be read
                self.reader = None
                continue

            data_size = cc_block[2]*8/4 # CC[2]*8 is data area size in bytes (/4 for blocks)
            messages = []
            data= []
            m_ptr = 4 # pointer to actual card memory location
            terminate = False
            errd = False
            while(m_ptr <= data_size+4 and not errd):
                msg = None
                if m_ptr > 255:
                    byte_one = math.floor(m_ptr/256)
                    byte_two = m_ptr%(byte_one*256)
                    msg = [0xFF, 0xB0, bytes([byte_one])[0], bytes([byte_two])[0], 0x01]
                else:
                    msg = [0xFF, 0xB0, 0x00, bytes([m_ptr])[0], 0x01]

                try:
                    block = self.send_transmission(card, msg)
                except RuntimeError as e:
                    self.logger.error("Error, empty block, reset reader 2")
                    self.reader = None
                    errd = True
                    break

                # decode TLV header
                tag, length, f_rem = self.parse_TLV_header(block)
                if length != 255:
                    m_ptr -= 1
                if tag == 'TERMINATOR':
                    terminate = True
                # now read the block of data into a record
                m_ptr += 1
                data = []
                for i in range(int(length/4)): # working with blocks
                    if errd:
                        break
                    msg = None
                    if m_ptr > 255:
                        byte_one = math.floor(m_ptr/256)
                        byte_two = m_ptr%(byte_one*256)
                        msg = [0xFF, 0xB0, bytes([byte_one])[0], bytes([byte_two])[0], 0x04]
                    else:
                        msg = [0xFF, 0xB0, 0x00, bytes([m_ptr])[0], 0x04]
                    try:
                        block = self.send_transmission(card, msg)
                    except RuntimeError as e:
                        self.logger.error("Error, empty block, reset reader 3")
                        self.reader = None
                        errd = True
                        break
                    data += block
                    m_ptr += 1

                amsg = None
                if tag == 'NDEF':
                    amsg = self.parse_NDEF_msg(data[f_rem:])
                    messages.append(amsg)

                for record in amsg:
                    _TYPE = 0
                    if record[_TYPE]:
                        terminate = True
                if terminate:
                    break


            attendee_id = None
            event_id = None
            salutation = None
            first_name = None 
            last_name = None
            middle_name = None
            _TYPE = 0
            _ID = 1
            _PAYLOAD = 2
            for message in messages:
                for record in message:
                    if record[_TYPE] == 'bcard.net:bcard' and len(record[_PAYLOAD])>40: # to avoid bcard url payloads
                        try:
                            (attendee_id, event_id, salutation, first_name, 
                                last_name, middle_name) = self.decode_bcard_payload(record[_PAYLOAD])
                        except Exception as e:
                            self.logger.error("Error decoding BCARD payload: {}".format(e))
            xdata = {
                'attendee_id': attendee_id,
                'event_id': event_id,
                'salutation': salutation,
                'first_name': first_name,
                'last_name': last_name,
                'middle_name': middle_name
            }
            msg = self.build_message(topic='scan_in', extendedData=xdata)
            self.logger.info('Sending message: {}'.format(msg))
            self.put_message(msg)

            self.reader = None

            # sleep for a bit to avoid double scanning
            time.sleep(5)

    def parse_TLV_header(self, barr):
        print('parsing TLV header bytes: ', barr)
        # return (tag, length (in bytes), [value] (if length != 0x00))
        try:
            tag = None
            length = None
            if barr[0] == 0x00: tag = 'NULL'
            if barr[0] == 0x03: tag = 'NDEF'
            if barr[0] == 0xFD: tag = 'PROPRIETARY'
            if barr[0] == 0xFE: tag = 'TERMINATOR'
            f_rem = 0

            if barr[1] != 0xFF: 
                print('NOT USING 3 BYTE FORMAT')
                length = barr[1]
                f_rem = 2
            else:
                length = struct.unpack('>h', bytes(barr[2:4]))[0]

        except Exception as e:
            print("Error parsing TLV header")
            return 0,0,0
        return tag, length, f_rem

    def parse_NDEF_header(self, barr):
        # parse ndef header
        # return  TNF(type name format), ID_LEN (ID length), 
        #         SR (short record bit), CF (chunk flag),
        #         ME (message end), MB (message begin), 

        #         TYPE_LEN (type length), PAY_LEN (payload length),
        #         ID (record type indicator)
        try:
            TNF = (0b00000111&barr[0])
            ID_LEN = (0b00001000&barr[0])>>3
            SR = (0b00010000&barr[0])>>4
            CF = (0b00100000&barr[0])>>5
            ME = (0b01000000&barr[0])>>6
            MB = (0b10000000&barr[0])>>7

            TYPE_LEN = barr[1]
            if SR:
                PAY_LEN = barr[2]
                PAY_TYPE = None
                REC_ID = None
                if TYPE_LEN > 0:
                    PAY_TYPE = bytearray(barr[3:3+TYPE_LEN]).decode('UTF-8')
                if ID_LEN > 0:
                    REC_ID = barr[3+TYPE_LEN:3+TYPE_LEN+ID_LEN]
            else:
                PAY_LEN = struct.unpack('>I', bytes(barr[2:6]))[0]
                PAY_TYPE = None
                if TYPE_LEN > 0:
                    PAY_TYPE = bytearray(barr[6:6+TYPE_LEN]).decode('UTF-8')
                REC_ID = None
                if ID_LEN > 0:
                    REC_ID = barr[6+TYPE_LEN:6+TYPE_LEN+ID_LEN]

            return (TNF, ID_LEN, SR, CF, ME, MB, TYPE_LEN, PAY_LEN, PAY_TYPE, REC_ID)
        except Exception as e:
            return (None, None, None, None, None, None, None, None, None, None)

    def parse_NDEF_msg(self, data):
        # iterate through the message bytes, reading ndef messages
        itr = 0
        records = []
        while itr < len(data):
            # get header first
            try:
                (TNF, ID_LEN, SR, CF, ME, MB, TYPE_LEN, PAY_LEN, 
                    PAY_TYPE, REC_ID) = self.parse_NDEF_header(data)
                if (TNF is None and 
                    ID_LEN is None and 
                    SR is None and 
                    CF is None and 
                    ME is None and 
                    MB is None and 
                    TYPE_LEN is None and 
                    PAY_LEN is None and 
                    PAY_TYPE is None and 
                    REC_ID is None):
                        return []
                itr += 6 + ID_LEN + TYPE_LEN

                rec_payload = data[itr:itr+PAY_LEN]
                itr += PAY_LEN

                record = [PAY_TYPE, REC_ID, rec_payload] # type, id, payload
                records.append(record)
            except Exception as e:
                self.logger.error('Error parsing NDEF message: {}'.format(e))
        return records

    def decode_bcard_payload(self, payload):
        # loop through decoding segments
        # each field separated by 0x1E
        # 6 fields: 
        fields = {
            'attendee_id': '', 
            'event_id': '', 
            'salutation': '', 
            'first_name': '',
            'last_name': '', 
            'middle_name': ''
        }
        field = 0
        for b in payload:
            try:
                if field == 0 and b == 30:
                    field += 1
                    continue
                elif b==31:
                    field += 1
                    if field >= len(list(fields.keys())): 
                        break
                    continue
                fields[list(fields.keys())[field]] += bytearray([b]).decode('UTF8')
            except:
                pass
        return tuple(fields.values())

    def establish_context(self):
        hresult, hcontext = SCardEstablishContext(SCARD_SCOPE_USER)
        if hresult != SCARD_S_SUCCESS:
            self.logger.error(
                'Unable to establish context: {}'.format(
                    SCardGetErrorMessage(hresult)))
            return
        self.context = hcontext

    def get_reader(self):
        hresult, readers = SCardListReaders(self.context, [])
        if hresult != SCARD_S_SUCCESS:
            self.logger.error(
                'Failed to list readers: {}'.format(
                    SCardGetErrorMessage(hresult)))
            return
        if len(readers)<1 or len(readers)-1<self._port:
            self.logger.error(
                'Not enough readers attached. {} needed, {} attached'.format(
                    (self._port+1), (len(readers))))
            return
        else:
            return readers[self._port]

    def get_card(self, mode=None, protocol=None):
        hresult, hcard, dwActiveProtocol = SCardConnect(
                self.context,
                self.reader,
                mode or SCARD_SHARE_SHARED, 
                protocol or (SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1))
        if hresult != SCARD_S_SUCCESS:
            return
        else:
            return hcard

    def send_transmission(self, card, msg, protocol=None):
        hresult, response = SCardTransmit(
                            card, 
                            protocol or SCARD_PCI_T1, 
                            msg)
        if hresult != SCARD_S_SUCCESS:
            self.logger.error(
                'Failed to send transmission: {}'.format(
                    SCardGetErrorMessage(hresult)))
            raise RuntimeError("Error sending transmission: {}".format(SCardGetErrorMessage(hresult)))
        else:
            return response[:-2]

    def listen(self):
        """
        Start thread to monitor inbound messages, declare module alive.
        """
        self.threadProcessQueue = Thread(target=self.process_queue)
        self.threadProcessQueue.setDaemon(True)
        self.threadProcessQueue.start()

    def build_message(self, topic, extendedData={}, recipients=['communication_modules']):
        """
        Create a Message instance.

        topic (required): message type
        sender_id (required): id property of original sender
        sender_type (optional): type of sender, ie. collection point type, module name, hostname, etc
        extended_data (optional): payload to deliver to recipient(s)
        recipients (optional): module name, which module(s) the message will be delivered to, ie. `websocket_server`.
                                use an array of strings to define multiple modules to send to.
                                use 'all' to send to all available modules.
                                use 'local_only' to send only to modules with `low_cost` prop set to True.
                                [DEFAULT] use 'communication_modules' to send only to communication modules.
                                use 'collection_modules' to send only to collection modules.
        """

        msg = Message(
            topic=topic,
            sender_id=self._id, 
            sender_type=self._type, 
            extended_data=extendedData, 
            recipients=recipients, 
            timestamp=datetime.datetime.utcnow())
        return msg

    def put_message(self, msg):
        """
        Put message onto outgoing queue.
        """
        print('putting message: ', msg)
        self.outQueue.put(msg)

    def process_queue(self):
        """
        Process inbound messages on separate thread.
        When a message is encountered, trigger an event to handle it.
        Sleep for some small amount of time to avoid overloading.
        Also receives a SHUTDOWN message from the main process when 
        the user presses the esc key.
        """

        self.logger.info("Starting to watch collection point inbound message queue")
        while self.alive:
            if (self.inQueue.empty() == False):
                self.logger.info("Queue size is %s" % self.inQueue.qsize())
                try:
                    message = self.inQueue.get(block=False,timeout=1)
                    if message is not None:
                        self.handle_message(message)
                except Exception as e:
                    self.logger.error("Error, unable to read queue: %s " %e)
                    self.shutdown()
                self.logger.info("Queue size is %s after" % self.inQueue.qsize())
            else:
                time.sleep(.25)

    def handle_message(self, message):
        """
        Handle messages from other modules to this one.
        Switch on the message topic, do something with the data fields.
        """
        if message.topic.upper()=='SHUTDOWN' and message.sender_id=='main':
            self.shutdown()

    def shutdown(self):
        """
        Shutdown the collection module.
        Set alive flag to false so it stops looping.
        Wait for things to die, then exit.
        """

        self.alive = False
        print("Shutting down nfc_bcard_reader")
        time.sleep(1)
        self.exit = True
