import os
import xml.parsers.expat
import operator


def message_crc(msg):
    from ..crc import x25crc
    crc = x25crc()
    crc.accumulate_str(msg.name + " ")
    for field in msg.ordered_fields:
        crc.accumulate_str(field.type + " ")
        crc.accumulate_str(field.name + " ")
        if field.array_length:
            crc.accumulate([field.array_length])
    return (crc.crc & 0xFF) ^ (crc.crc >> 8)


class HippoType(object):
    def __init__(self, name, id, linenumber, description=""):
        self.name = name
        self.name_lower = name.lower()
        self.linenumber = linenumber
        self.id = int(id)
        self.description = description
        self.fields = []
        self.fieldlengths = []
        self.fieldtypes = []
        self.ordered_fieldtypes = []
        self.fieldnames = []
        self.ordered_fieldnames = []
        self.wire_length = 0
        self.field_offsets = {}

    def sort_fields(self):
        self.ordered_fields = sorted(self.fields,
                                     key=operator.attrgetter("type_length"),
                                     reverse=True)

    def update_fieldnames(self):
        self.fieldnames = []
        for field in self.fields:
            self.fieldnames.append(field.name)

    def update_fieldlenghts(self):
        self.fieldlengths = []
        for field in self.fields:
            length = field.array_length
            if not length:
                self.fieldlengths.append(1)
            elif length > 1 and field.type == "char":
                self.fieldlengths.append(1)
            else:
                self.fieldlengths.append(length)

    def update_fieldtypes(self):
        self.fieldtypes = []
        for field in self.fields:
            self.fieldtypes.append(field.type)

    def update_field_offsets(self):
        self.field_offsets = {}
        self.wire_length = 0
        for i, field in enumerate(self.ordered_fields):
            field.wire_offset = self.wire_length
            self.field_offsets[field.name] = field.wire_offset
            self.wire_length += field.wire_length
            self.ordered_fieldnames.append(field.name)
            self.ordered_fieldtypes.append(field.type)

    def update_crc(self):
        self.crc_extra = message_crc(self)

    def update_all_field_properties(self):
        self.update_fieldlenghts()
        self.update_fieldnames()
        self.update_fieldtypes()
        self.sort_fields()
        self.update_field_offsets()
        self.update_crc()


class HippoField(object):
    def __init__(self,
                 name,
                 type,
                 print_format,
                 xml,
                 description="",
                 enum="",
                 display="",
                 units=""):
        self.name = name
        self.name_upper = name.upper()
        self.description = description
        self.array_length = 0
        self.enum = enum
        self.display = display
        self.units = units
        self.omit_arg = False
        self.const_value = None
        self.print_format = print_format
        lengths = dict(
            float=4,
            double=8,
            char=1,
            int8_t=1,
            uint8_t=1,
            int16_t=2,
            uint16_t=2,
            int32_t=4,
            uint32_t=4,
            int64_t=8,
            uint64_t=8,
        )

        idx = type.find("[")
        if idx != -1:
            assert type[-1:] == "]"
            self.array_length = int(type[idx + 1:-1])
            type = type[:idx]
            if type == "array":
                type = "int8_t"
        if type in lengths:
            self.type_length = lengths[type]
            self.type = type
        elif (type + "_t") in lengths:
            self.type_length = lengths[type + "_t"]
            self.type = type + "_t"
        else:
            raise Exception()
        if self.array_length != 0:
            self.wire_length = self.array_length * self.type_length
        else:
            self.wire_length = self.type_length
        self.type_upper = self.type.upper()


class HippoXml(object):
    def __init__(self, filename):
        self.filename = filename
        self.basename = os.path.basename(filename)
        self.basename_upper = self.basename.upper()
        self.message = []
        self.in_element_list = []
        with open(filename, "rb") as f:
            self.p = xml.parsers.expat.ParserCreate()
            self.p.StartElementHandler = self.start_element
            self.p.EndElementHandler = self.end_element
            self.p.CharacterDataHandler = self.element_text
            self.p.ParseFile(f)
        self.message_lengths = {}
        self.message_crcs = {}
        self.message_names = {}
        self.largest_payload = 0

        for msg in self.message:
            print(msg.name)
            msg.update_all_field_properties()
            key = msg.id
            self.message_crcs[key] = msg.crc_extra
            self.message_lengths[key] = msg.wire_length
            self.message_names[key] = msg.name
            if msg.wire_length > self.largest_payload:
                self.largest_payload = msg.wire_length

    def check_attrs(self, attrs, check, where):
        for c in check:
            if c not in attrs:
                raise Exception(
                    "Expected missing {} '{}' attribute at {}:{}".format(
                        where, c, self.filename, self.p.CurrentLineNumber))

    def start_element(self, name, attrs):
        self.in_element_list.append(name)
        in_element = ".".join(self.in_element_list)
        if in_element == "hippolink.messages.message":
            self.check_attrs(attrs, ["name", "id"], "message")
            self.message.append(
                HippoType(attrs["name"], attrs["id"],
                          self.p.CurrentLineNumber))
        elif in_element == "hippolink.messages.message.field":
            self.check_attrs(attrs, ["name", "type"], "field")
            print_format = attrs.get("print_format", None)
            units = attrs.get("units", "")
            if units:
                units = "[" + units + "]"
            new_field = HippoField(name=attrs["name"],
                                   type=attrs["type"],
                                   print_format=print_format,
                                   xml=self,
                                   units=units)
            self.message[-1].fields.append(new_field)

    def end_element(self, name):
        self.in_element_list.pop()

    def element_text(self, text):
        in_element = ".".join(self.in_element_list)
        if in_element == "hippolink.messages.message.description":
            self.message[-1].description += text
        elif in_element == "hippolink.messages.message.field":
            self.message[-1].fields[-1].description += text
