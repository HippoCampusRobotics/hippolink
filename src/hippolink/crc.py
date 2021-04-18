class x25crc(object):
    '''CRC-16/MCRF4XX - based on checksum.h from mavlink library'''
    def __init__(self, buf=None):
        self.crc = 0xffff
        if buf is not None:
            if isinstance(buf, str):
                self.accumulate_str(buf)
            else:
                self.accumulate(buf)

    def accumulate(self, buf):
        '''add in some more bytes'''
        accum = self.crc
        for b in buf:
            tmp = b ^ (accum & 0xff)
            tmp = (tmp ^ (tmp << 4)) & 0xFF
            accum = (accum >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)
        self.crc = accum

    def accumulate_str(self, buf):
        '''add in some more bytes'''
        try:  # if buf is bytes
            bytes_array = bytearray(buf)
        except TypeError:  # if buf is str
            bytes_array = bytearray(buf.encode())
        self.accumulate(bytes_array)