import struct

from . import msgs
from . import cobs
from .crc import x25crc


class HippoLinkError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)
        self.message = msg


class HippoLink_bad_data(msgs.HippoLinkMessage):
    def __init__(self, data, reason):
        super(HippoLink_bad_data,
              self).__init__(msgs.HIPPOLINK_MSG_ID_BAD_DATA, "BAD_DATA")
        self._fieldnames = ["data", "reason"]
        self.data = data
        self.reason = reason
        self._msg_buffer = data

    def __str__(self):
        return '%s {%s, data:%s}' % (self._type, self.reason, [('%x' % ord(i) if isinstance(i, str) else '%x' % i) for i in self.data])


class HippoLink(object):
    def __init__(self, port, node_id):
        self.port = port
        self.node_id = node_id
        self.send_callback = None
        self.send_callback_args = None
        self.send_callback_kwargs = None
        self.buffer = bytearray()
        self.buffer_index = 0
        self.link_stats = dict(bytes_sent=0,
                               packets_sent=0,
                               bytes_received=0,
                               packets_received=0,
                               receive_errors=0)
        self.header_unpacker = struct.Struct("<BBB")
        self.crc_unpacker = struct.Struct("<H")
        self.header_len = self.header_unpacker.size
        self.crc_len = self.crc_unpacker.size

    def set_send_callback(self, callback, *args, **kwargs):
        self.send_callback = callback
        self.send_callback_args = args
        self.send_callback_kwargs = kwargs

    def _update_link_stats_sent(self, msg_len):
        self.link_stats["bytes_sent"] += msg_len
        self.link_stats["packets_sent"] += 1

    def _update_link_stats_received(self, msg_len):
        self.link_stats["bytes_received"] += msg_len
        self.link_stats["packets_received"] += 1

    def _update_link_stats_errors(self):
        self.link_stats["receive_errors"] += 1

    def send(self, msg):
        packed_msg = msg.pack(self)
        encoded_msg = cobs.encode(packed_msg)
        self.port.write(encoded_msg)
        self._update_link_stats_sent(len(encoded_msg))
        if self.send_callback:
            self.send_callback(msg, *self.send_callback_args,
                               **self.send_callback_kwargs)

    def decode(self, msg_buffer):
        header_len = self.header_len
        crc_len = self.crc_len
        try:
            msg_len, node_id, msg_id = self.header_unpacker.unpack(
                msg_buffer[:header_len])
        except struct.error as e:
            raise HippoLinkError(
                "Unable to unpack HippoLink header: {}".format(e))

        payload_len = len(msg_buffer) - (header_len + crc_len)
        if msg_len != payload_len:
            raise HippoLinkError(
                "Invalid HippoLink message length(msg_id={}). Got {} but "
                "expected {}.".format(msg_id, payload_len, msg_len))
        if msg_id not in msgs.HIPPOLINK_MAP:
            raise HippoLinkError("Unknown message ID {}".format(msg_id))

        msg_type = msgs.HIPPOLINK_MAP[msg_id]
        fmt = msg_type.format
        order_map = msg_type.orders
        len_map = msg_type.lengths
        crc_extra = msg_type.crc_extra

        try:
            crc, = self.crc_unpacker.unpack(msg_buffer[-crc_len:])
        except struct.error as e:
            raise HippoLinkError("Unable to unpack CRC: {}".format(e))
        crc_buffer = msg_buffer[:-crc_len]
        crc_buffer.append(crc_extra)
        crc_check = x25crc(crc_buffer)
        if crc != crc_check.crc:
            raise HippoLinkError("Invalid CRC(msg_id={}) is 0x{:04x} but "
                                 "should be 0x{:04x}.".format(
                                     msg_id, crc, crc_check.crc))

        csize = msg_type.unpacker.size
        payload_buffer = msg_buffer[header_len:-crc_len]
        if len(payload_buffer) < csize:
            payload_buffer.extend([0] * (csize - len(payload_buffer)))
        payload_buffer = payload_buffer[:csize]
        try:
            fields = msg_type.unpacker.unpack(payload_buffer)
        except struct.error as e:
            raise HippoLinkError("Unable to unpack payload (type={}, "
                                 "fmt={}, payload_len={}): {}".format(
                                     msg_type, fmt, len(payload_buffer), e))

        fieldlist = list(fields)
        fields = fieldlist[:]
        if sum(len_map) == len(len_map):
            # message has no arrays
            for i in range(len(fieldlist)):
                fieldlist[i] = fields[order_map[i]]
        else:
            fieldlist = []
            for i in range(len(order_map)):
                order = order_map[i]
                L = len_map[order]
                tip = sum(len_map[:order])
                field = fields[tip]
                if L == 1 or isinstance(field, str):
                    fieldlist.append(field)
                else:
                    fieldlist.append(fields[tip:tip + L])

        # TODO: handle strings

        fields = tuple(fieldlist)
        try:
            msg = msg_type(*fields)
        except Exception as e:
            raise HippoLinkError("Unable to instantiate HippoLink message: "
                                 "{}".format(e))
        msg._msg_buffer = msg_buffer
        msg._payload = msg_buffer[header_len:-crc_len]
        msg._crc = crc
        msg._header = msgs.HippoLinkHeader(msg_id=msg_id,
                                           msg_len=msg_len,
                                           node_id=node_id)
        return msg

    def recv_msg(self):
        data = self.port.read_until(expected=bytearray([0, ]))
        if not data or data[-1] != 0 or len(data) < self.crc_len + self.header_len + 2:
            return None
        data = cobs.decode(data)
        if len(data) < self.header_len + self.crc_len:
            self._update_link_stats_errors()
            msg = HippoLink_bad_data(bytearray(data),
                                     "Message shorter than overhead.")
            return msg
        try:
            msg = self.decode(data)
        except HippoLinkError as e:
            msg = HippoLink_bad_data(data, e.message)
            self._update_link_stats_errors()
        else:
            self._update_link_stats_received(len(msg._msg_buffer))
        return msg
