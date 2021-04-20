def encode(data):
    output = bytearray(len(data) + 2)
    dst_index = 1
    zero_offset = 1
    for src_byte in data:
        if src_byte == 0:
            output[dst_index - zero_offset] = zero_offset
            zero_offset = 1
        else:
            output[dst_index] = src_byte
            zero_offset += 1
        dst_index += 1
    output[dst_index - zero_offset] = zero_offset
    output[dst_index] = 0
    return output


def decode(data):
    if data[-1] == 0:
        data = data[:-1]
    output = bytearray()
    index = 1
    offset = data[0] - 1
    while index < len(data):
        if offset == 0:
            output.append(0)
            offset = data[index]
        else:
            output.append(data[index])
        index += 1
        offset -= 1
    return output
