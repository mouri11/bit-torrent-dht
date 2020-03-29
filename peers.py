import time, socket, struct, bitstring,logging
from pubsub import pub

import msg


class Peers(object):
    def __init__(self, no_of_pieces, ip, port=6881):
        self.last_call = 0.0
        self.has_handshaked = False
        self.healthy = False
        self.read_buffer = b''
        self.socket = None
        self.ip = ip
        self.port = port
        self.no_of_pieces = no_of_pieces
        self.bit_field = bitstring.BitArray(number_of_pieces)
        self.state = {
            'am_choking': True,
            'am_interested': False,
            'peer_choking': True,
            'peer_interested': False,
        }

    def __hash__(self):
        return "%s:%d" % (self.ip, self.port)

    def conn(self):
        try:
            self.socket = socket.create_connection((self.ip, self.port), timeout=2)
            self.socket.setblocking(False)
            logging.debug("Connected to peer ip: {} - port: {}".format(self.ip, self.port))
            self.healthy = True

        except Exception as e:
            print("Failed to connect to peer (ip: %s - port: %s - %s)" % (self.ip, self.port, e.__str__()))
            return False

        return True

    def send_to_peer(self, msg):
        try:
            self.socket.send(msg)
            self.last_call = time.time()
        except Exception as e:
            self.healthy = False
            logging.error("Failed to send to peer : %s" % e.__str__())

    def is_interested(self):
        return self.state['peer_interested']

    def am_interested(self):
        return self.state['am_interested']

    def is_eligible(self):
        return (time.time() - self.last_call) > 0.2

    def has_piece(self, index):
        return self.bit_field[index]

     def is_choking(self):
        return self.state['peer_choking']

    def is_unchoked(self):
        return not self.is_choking()

    def am_choking(self):
        return self.state['am_choking']

    def am_unchoking(self):
        return not self.am_choking()

    def handle_choke(self):
        logging.debug('handle_choke - %s' % self.ip)
        self.state['peer_choking'] = True

    def handle_unchoke(self):
        logging.debug('handle_unchoke - %s' % self.ip)
        self.state['peer_choking'] = False

    def handle_request(self, rqst):
        """
        :type request: message.Request
        """
        logging.debug('handle_request - %s' % self.ip)
        if self.is_interested() and self.is_unchoked():
            pub.sendMessage('PiecesMgr.PeerRqstsPiece', request=rqst, peer=self)

    def handle_piece(self, msg):
        """
        :type message: message.Piece
        """
        pub.sendMessage('PiecesManager.Piece', piece=(msg.piece_index, msg.block_offset, msg.block))

    def handle_cancel(self):
        logging.debug('handle_cancel - %s' % self.ip)

    def handle_port_request(self):
        logging.debug('handle_port_request - %s' % self.ip)

    def _handle_handshake(self):
        try:
            handshake_message = msg.Handshake.from_bytes(self.read_buffer)
            self.has_handshaked = True
            self.read_buffer = self.read_buffer[handshake_message.total_length:]
            logging.debug('handle_handshake - %s' % self.ip)
            return True

        except Exception:
            logging.exception("First message should always be a handshake message")
            self.healthy = False

        return False

    def _handle_keep_alive(self):
        try:
            keep_alive = msg.KeepAlive.from_bytes(self.read_buffer)
            logging.debug('handle_keep_alive - %s' % self.ip)
        except msg.WrongMessageException:
            return False
        except Exception:
            logging.exception("Error KeepALive, (need at least 4 bytes : {})".format(len(self.read_buffer)))
            return False

        self.read_buffer = self.read_buffer[keep_alive.total_length:]
        return True

    def handle_interested(self):
        logging.debug('handle_interested - %s' % self.ip)
        self.state['peer_interested'] = True

        if self.am_choking():
            unchoke = msg.UnChoke().to_bytes()
            self.send_to_peer(unchoke)

    def handle_not_interested(self):
        logging.debug('handle_not_interested - %s' % self.ip)
        self.state['peer_interested'] = False

    def handle_have(self, have):
        """
        :type have: message.Have
        """
        logging.debug('handle_have - ip: %s - piece: %s' % (self.ip, have.piece_index))
        self.bit_field[have.piece_index] = True

        if self.is_choking() and not self.state['am_interested']:
            interested = msg.Interested().to_bytes()
            self.send_to_peer(interested)
            self.state['am_interested'] = True

    def handle_bitfield(self, bitfield):
        """
        :type bitfield: message.BitField
        """
        logging.debug('handle_bitfield - %s - %s' % (self.ip, bitfield.bitfield))
        self.bit_field = bitfield.bitfield

        if self.is_choking() and not self.state['am_interested']:
            interested = msg.Interested().to_bytes()
            self.send_to_peer(interested)
            self.state['am_interested'] = True

    def get_messages(self):
        while len(self.read_buffer) > 4 and self.healthy:
            if (not self.has_handshaked and self._handle_handshake()) or self._handle_keep_alive():
                continue

            payload_length, = struct.unpack(">I", self.read_buffer[:4])
            total_length = payload_length + 4

            if len(self.read_buffer) < total_length:
                break
            else:
                payload = self.read_buffer[:total_length]
                self.read_buffer = self.read_buffer[total_length:]

            try:
                m = msg.MessageDispatcher(payload).dispatch()
                if m:
                    yield m
            except msg.WrongMessageException:
                logging.exception("")