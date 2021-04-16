class MAVXML(object):
    '''parse a mavlink XML file'''
    def __init__(self, filename, wire_protocol_version=PROTOCOL_0_9):
        self.filename = filename
        self.basename = os.path.basename(filename)
        if self.basename.lower().endswith(".xml"):
            self.basename = self.basename[:-4]
        self.basename_upper = self.basename.upper()
        self.message = []
        self.enum = []
        # we use only the day for the parse_time, as otherwise
        # it causes a lot of unnecessary cache misses with ccache
        self.parse_time = time.strftime("%a %b %d %Y")
        self.version = 2
        self.include = []
        self.wire_protocol_version = wire_protocol_version

        # setup the protocol features for the requested protocol version
        if wire_protocol_version == PROTOCOL_0_9:
            self.protocol_marker = ord('U')
            self.sort_fields = False
            self.little_endian = False
            self.crc_extra = False
            self.crc_struct = False
            self.command_24bit = False
            self.allow_extensions = False
        elif wire_protocol_version == PROTOCOL_1_0:
            self.protocol_marker = 0xFE
            self.sort_fields = True
            self.little_endian = True
            self.crc_extra = True
            self.crc_struct = False
            self.command_24bit = False
            self.allow_extensions = False
        elif wire_protocol_version == PROTOCOL_2_0:
            self.protocol_marker = 0xFD
            self.sort_fields = True
            self.little_endian = True
            self.crc_extra = True
            self.crc_struct = True
            self.command_24bit = True
            self.allow_extensions = True
        else:
            print("Unknown wire protocol version")
            print("Available versions are: %s %s" % (PROTOCOL_0_9, PROTOCOL_1_0, PROTOCOL_2_0))
            raise MAVParseError('Unknown MAVLink wire protocol version %s' % wire_protocol_version)

        in_element_list = []

        def check_attrs(attrs, check, where):
            for c in check:
                if c not in attrs:
                    raise MAVParseError('expected missing %s "%s" attribute at %s:%u' % (
                        where, c, filename, p.CurrentLineNumber))

        def start_element(name, attrs):
            in_element_list.append(name)
            in_element = '.'.join(in_element_list)
            #print in_element
            if in_element == "mavlink.messages.message":
                check_attrs(attrs, ['name', 'id'], 'message')
                self.message.append(MAVType(attrs['name'], attrs['id'], p.CurrentLineNumber))
            elif in_element == "mavlink.messages.message.extensions":
                self.message[-1].extensions_start = len(self.message[-1].fields)
            elif in_element == "mavlink.messages.message.field":
                check_attrs(attrs, ['name', 'type'], 'field')
                print_format = attrs.get('print_format', None)
                enum = attrs.get('enum', '')
                display = attrs.get('display', '')
                units = attrs.get('units', '')
                if units:
                    units = '[' + units + ']'
                instance = attrs.get('instance', False)
                new_field = MAVField(attrs['name'], attrs['type'], print_format, self, enum=enum, display=display, units=units, instance=instance)
                if self.message[-1].extensions_start is None or self.allow_extensions:
                    self.message[-1].fields.append(new_field)
            elif in_element == "mavlink.enums.enum":
                check_attrs(attrs, ['name'], 'enum')
                self.enum.append(MAVEnum(attrs['name'], p.CurrentLineNumber))
            elif in_element == "mavlink.enums.enum.entry":
                check_attrs(attrs, ['name'], 'enum entry')
                # determine value and if it was automatically assigned (for possible merging later)
                if 'value' in attrs:
                    value = eval(attrs['value'])
                    autovalue = False
                else:
                    value = self.enum[-1].highest_value + 1
                    autovalue = True
                # check lowest value
                if (self.enum[-1].start_value is None or value < self.enum[-1].start_value):
                    self.enum[-1].start_value = value
                # check highest value
                if (value > self.enum[-1].highest_value):
                    self.enum[-1].highest_value = value
                # append the new entry
                self.enum[-1].entry.append(MAVEnumEntry(attrs['name'], value, '', False, autovalue, self.filename, p.CurrentLineNumber))
            elif in_element == "mavlink.enums.enum.entry.param":
                check_attrs(attrs, ['index'], 'enum param')
                self.enum[-1].entry[-1].param.append(
                                                MAVEnumParam(attrs['index'], 
                                                        label=attrs.get('label', ''), units=attrs.get('units', ''), 
                                                        enum=attrs.get('enum', ''), increment=attrs.get('increment', ''), 
                                                        minValue=attrs.get('minValue', ''), 
                                                        maxValue=attrs.get('maxValue', ''), default=attrs.get('default', '0'), 
                                                        reserved=attrs.get('reserved', False) ))

        def is_target_system_field(m, f):
            if f.name == 'target_system':
                return True
            if m.name == "MANUAL_CONTROL" and f.name == "target":
                return True
            return False

        def end_element(name):
            in_element_list.pop()

        def char_data(data):
            in_element = '.'.join(in_element_list)
            if in_element == "mavlink.messages.message.description":
                self.message[-1].description += data
            elif in_element == "mavlink.messages.message.field":
                if self.message[-1].extensions_start is None or self.allow_extensions:
                    self.message[-1].fields[-1].description += data
            elif in_element == "mavlink.enums.enum.description":
                self.enum[-1].description += data
            elif in_element == "mavlink.enums.enum.entry.description":
                self.enum[-1].entry[-1].description += data
            elif in_element == "mavlink.enums.enum.entry.param":
                self.enum[-1].entry[-1].param[-1].description += data
            elif in_element == "mavlink.version":
                self.version = int(data)
            elif in_element == "mavlink.include":
                self.include.append(data)

        f = open(filename, mode='rb')
        p = xml.parsers.expat.ParserCreate()
        p.StartElementHandler = start_element
        p.EndElementHandler = end_element
        p.CharacterDataHandler = char_data
        p.ParseFile(f)
        f.close()
   

        #Post process to add reserved params (for docs)
        for current_enum in self.enum:
            if not 'MAV_CMD' in current_enum.name:
                continue
            for enum_entry in current_enum.entry:
                if len(enum_entry.param) == 7:
                    continue
                params_dict=dict()
                for param_index in range (1,8):
                    params_dict[param_index] = MAVEnumParam(param_index, label='', units='', enum='', increment='', 
                                                        minValue='', maxValue='', default='0', reserved='True')

                for a_param in enum_entry.param:
                    params_dict[int(a_param.index)] = a_param
                enum_entry.param=params_dict.values()
                


        self.message_lengths = {}
        self.message_min_lengths = {}
        self.message_flags = {}
        self.message_target_system_ofs = {}
        self.message_target_component_ofs = {}
        self.message_crcs = {}
        self.message_names = {}
        self.largest_payload = 0

        if not self.command_24bit:
            # remove messages with IDs > 255
            m2 = []
            for m in self.message:
                if m.id <= 255:
                    m2.append(m)
                else:
                    print("Ignoring MAVLink2 message %s" % m.name)
            self.message = m2

        for m in self.message:
            if not self.command_24bit and m.id > 255:
                continue

            m.wire_length = 0
            m.wire_min_length = 0
            m.fieldnames = []
            m.fieldlengths = []
            m.ordered_fieldnames = []
            m.ordered_fieldtypes = []
            m.fieldtypes = []
            m.message_flags = 0
            m.target_system_ofs = 0
            m.target_component_ofs = 0
            m.field_offsets = {}
            
            if self.sort_fields:
                # when we have extensions we only sort up to the first extended field
                sort_end = m.base_fields()
                m.ordered_fields = sorted(m.fields[:sort_end],
                                                   key=operator.attrgetter('type_length'),
                                                   reverse=True)
                m.ordered_fields.extend(m.fields[sort_end:])
            else:
                m.ordered_fields = m.fields
            for f in m.fields:
                m.fieldnames.append(f.name)
                L = f.array_length
                if L == 0:
                    m.fieldlengths.append(1)
                elif L > 1 and f.type == 'char':
                    m.fieldlengths.append(1)
                else:
                    m.fieldlengths.append(L)
                m.fieldtypes.append(f.type)
            for i in range(len(m.ordered_fields)):
                f = m.ordered_fields[i]
                f.wire_offset = m.wire_length
                m.field_offsets[f.name] = f.wire_offset
                m.wire_length += f.wire_length
                field_el_length = f.wire_length
                if f.array_length > 1:
                    field_el_length = f.wire_length / f.array_length
                if f.wire_offset % field_el_length != 0:
                    # misaligned field, structure will need packing in C
                    m.needs_pack = True
                if m.extensions_start is None or i < m.extensions_start:
                    m.wire_min_length = m.wire_length
                m.ordered_fieldnames.append(f.name)
                m.ordered_fieldtypes.append(f.type)
                f.set_test_value()
                if f.name.find('[') != -1:
                    raise MAVParseError("invalid field name with array descriptor %s" % f.name)
                # having flags for target_system and target_component helps a lot for routing code
                if is_target_system_field(m, f):
                    m.message_flags |= FLAG_HAVE_TARGET_SYSTEM
                    m.target_system_ofs = f.wire_offset
                elif f.name == 'target_component':
                    m.message_flags |= FLAG_HAVE_TARGET_COMPONENT
                    m.target_component_ofs = f.wire_offset
            m.num_fields = len(m.fieldnames)
            if m.num_fields > 64:
                raise MAVParseError("num_fields=%u : Maximum number of field names allowed is" % (
                    m.num_fields, 64))
            m.crc_extra = message_checksum(m)

            key = m.id
            self.message_crcs[key] = m.crc_extra
            self.message_lengths[key] = m.wire_length
            self.message_min_lengths[key] = m.wire_min_length
            self.message_names[key] = m.name
            self.message_flags[key] = m.message_flags
            self.message_target_system_ofs[key] = m.target_system_ofs
            self.message_target_component_ofs[key] = m.target_component_ofs

            if m.wire_length > self.largest_payload:
                self.largest_payload = m.wire_length

    def __str__(self):
        return "MAVXML for %s from %s (%u message, %u enums)" % (
            self.basename, self.filename, len(self.message), len(self.enum))
