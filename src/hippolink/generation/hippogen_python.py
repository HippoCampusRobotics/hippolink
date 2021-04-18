#!/usr/bin/env python

import textwrap


def generate_preamble(f):
    f.write("""
# Auto-generated.

from __future__ import print_function
import struct
import json
from hippolink.crc import x25crc

def to_string(s):
    try:
        return s.decode("utf-8")
    except Exception:
        pass
    try:
        s2 = s.encode("utf-8", "ignore")
        x = u"%s" % s2
        return s2
    except Exception:
        pass
    r = ""
    try:
        for c in s:
            r2 = r + c
            r2 = r2.encode("ascii", "ignore")
            x = u"%s" % r2
            r = r2
    except Exception:
        pass
    return r+ "_XXX"

class HippoLinkHeader(object):
    def __init__(self, msg_id, msg_len=0, seq=0, node_id=0):
        self.msg_len = msg_len
        self.seq = seq
        self.node_id = node_id
        self.msg_id = msg_id

    def pack(self):
        return struct.pack("<BBBB", self.msg_len, self.seq, self.node_id, self.msg_id)

class HippoLinkMessage(object):
    def __init__(self, msg_id, name):
        self._header = HippoLinkHeader(msg_id=msg_id)
        self._payload = None
        self._msg_buffer = None
        self._crc = None
        self._fieldnames = []
        self._type = name

    def format_attr(self, field):
        raw_attr = getattr(self, field)
        if isinstance(raw_attr, bytes):
            raw_attr = to_string(raw_attr).rstrip("\\00")
        return raw_attr
    
    def get_msg_buffer(self):
        if isinstance(self._msg_buffer, bytearray):
            return self._msg_buffer
        return bytearray(self._msg_buffer)
    
    def get_header(self):
        return self._header

    def get_payload(self):
        return self._payload
    
    def get_crc(self):
        return self._crc
    
    def get_fieldnames(self):
        return self._fieldnames

    def get_type(self):
        return self._type

    def get_msg_id(self):
        return self._header.msg_id

    def get_node_id(self):
        return self._header.node_id

    def get_seq(self):
        return self._header.seq

    def __str__(self):
        ret = "%s {" % self._type
        for name in self._fieldnames:
            value = self.format_attr(name)
            ret += "%s : %s" % (name, value)
        ret = ret[0:-2] + "}"
        return ret

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if other is None:
            return False
        if self.get_type() != other.get_type():
            return False

        if self.get_seq() != other.get_seq():
            return False
        if self.get_node_id() != other.node_id():
            return False
        for name in self._fieldnames:
            if self.format_attr(name) != other.format_attr(a):
                return False
        return True

    def to_dict(self):
        d = dict()
        d["type"] = self._type
        for name in self._fieldnames:
            d[name] = self.format_attr(name)
        return d

    def to_json(self):
        return json.dumps(self.to_dict())

    def pack(self, hippo, crc_extra, payload):
        n = len(payload)
        nullbyte = chr(0)
        if str(type(payload)) == "<class 'bytes'>":
            nullbyte = 0
        # truncate trailing zeros
        while n > 1 and payload[n-1] == nullbyte:
            n -= 1
        self._payload = payload[:n]
        self._header = HippoLinkHeader(msg_id=self._header.msg_id, msg_len=len(self._payload), seq=hippo.seq, node_id=hippo.node_id)
        self._msg_buffer = self._header.pack() + self._payload
        crc = x25crc(self._msg_buffer)
        crc.accumulate_str(self._msg_buffer)
        self.crc = crc.crc
        self._msgbuf += struct.pack("<H", self._crc)
        return self._msgbuf

    def __getitem(self, key):
        if self._instances is None:
            raise IndexError()
        if key not in self._instances:
            raise IndexError()
        return self._instances[key]
""")


def byname_hash_from_field_attribute(msg, attribute):
    strings = []
    for field in msg.fields:
        value = getattr(field, attribute, None)
        if value is None:
            value == ""
        if attribute == "units":
            value = value.lstrip("[")
            value = value.rstrip("]")
        strings.append("'{}': '{}'".format(field.name, value))
    return ", ".join(strings)


def generate_message_ids(f, msgs):
    print("Generating message IDs.")
    f.write("\n# message IDs\n")
    f.write("HIPPOLINK_MSG_ID_BAD_DATA = -1\n")
    for msg in msgs:
        f.write("HIPPOLINK_MSG_ID_{} = {}\n".format(msg.name.upper(), msg.id))


def generate_classes(f, msgs):
    print("Generating message class definitions.")
    wrapper = textwrap.TextWrapper(initial_indent="    ",
                                   subsequent_indent="    ")
    for msg in msgs:
        classname = "HippoLink_{}_message".format(msg.name.lower())
        fieldname_str = ", ".join(["'{}'".format(s) for s in msg.fieldnames])
        ordered_fieldname_str = ", ".join(
            ["'{}'".format(s) for s in msg.ordered_fieldnames])
        fielddisplays_str = byname_hash_from_field_attribute(msg, "display")
        fieldenums_str = byname_hash_from_field_attribute(msg, "enum")
        fieldunits_str = byname_hash_from_field_attribute(msg, "units")

        fieldtypes_str = ", ".join(["'{}'".format(s) for s in msg.fieldtypes])

        f.write("""
class {classname}(HippoLinkMessage):
    '''
{description}
    '''
    id = HIPPOLINK_MSG_ID_{id}
    name = '{name}'
    fieldnames = [{fieldname_str}]
    ordered_fieldnames = [{ordered_fieldname_str}]
    fielddisplays_by_name = {{{fielddisplays_str}}}
    fieldenums_by_name = {{{fieldenums_str}}}
    fieldunits_by_name = {{{fieldunits_str}}}
    format = '{fmtstr}'
    orders = {order_map}
    lengths = {len_map}
    array_lengths = {array_len_map}
    crc_extra = {crc_extra}
    unpacker = struct.Struct('{fmtstr}')
    
    def __init__(self""".format(
            classname=classname,
            description=wrapper.fill(msg.description.strip()),
            id=msg.name.upper(),
            name=msg.name.upper(),
            fieldname_str=fieldname_str,
            ordered_fieldname_str=ordered_fieldname_str,
            fielddisplays_str=fielddisplays_str,
            fieldenums_str=fieldenums_str,
            fieldunits_str=fieldunits_str,
            fmtstr=msg.fmtstr,
            order_map=msg.order_map,
            len_map=msg.len_map,
            array_len_map=msg.array_len_map,
            crc_extra=msg.crc_extra,
        ))
        for i in range(len(msg.fields)):
            fname = msg.fieldnames[i]

            f.write(", {}".format(fname))
        f.write("):\n")
        f.write("        super({classname}, self).__init__(msg_id="
                "{classname}.id, name={classname}.name)\n".format(
                    classname=classname))
        f.write("        self._fieldnames = {classname}.fieldnames\n".format(
            classname=classname))
        for field in msg.fields:
            f.write("        self.{name} = {name}\n".format(name=field.name))
        f.write("""
    def pack(self, hippo):
        return HippoLinkMessage.pack(self, hippo, {crc_extra}, struct.pack('{fmtstr}'"""
                .format(crc_extra=msg.crc_extra, fmtstr=msg.fmtstr))
        for field in msg.ordered_fields:
            if field.type != "char" and field.array_length > 1:
                for i in range(field.array_length):
                    f.write(", self.{name}[{index}]".format(name=field.name,
                                                            index=i))
            else:
                f.write(", self.{name}".format(name=field.name))
        f.write("))\n")


def hippofmt(field):
    map = dict(
        float="f",
        double="d",
        char="c",
        int8_t="b",
        uint8_t="B",
        int16_t="h",
        uint16_t="H",
        int32_t="i",
        uint32_t="I",
        int64_t="q",
        uint64_t="Q",
    )
    if field.array_length:
        if field.type == "char":
            return str(field.array_length) + "s"
        return str(field.array_length) + map[field.type]
    return map[field.type]


def hippodefault(field):
    if field.type == "char":
        default_value = "''"
    else:
        default_value = "0"
    if field.array_length == 0:
        return default_value
    return "[" + ", ".join([default_value] * field.array_length) + "]"


def generate(xml, out_path):
    filename = out_path
    msgs = []
    for x in xml:
        msgs.extend(x.message)
    for msg in msgs:
        msg.fielddefaults = []
        msg.fmtstr = "<"
        for field in msg.ordered_fields:
            msg.fmtstr += hippofmt(field)
            msg.fielddefaults.append(hippodefault(field))
        msg.order_map = [0] * len(msg.fieldnames)
        msg.len_map = [0] * len(msg.fieldnames)
        msg.array_len_map = [0] * len(msg.fieldnames)
        for i in range(len(msg.fieldnames)):
            msg.order_map[i] = msg.ordered_fieldnames.index(msg.fieldnames[i])
            msg.array_len_map[i] = msg.ordered_fields[i].array_length
            n = msg.order_map[i]
            msg.len_map[n] = msg.fieldlengths[i]
    with open(filename, "w") as f:
        generate_preamble(f)
        generate_message_ids(f, msgs)
        generate_classes(f, msgs)