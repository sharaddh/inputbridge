import json
from typing import Any, Dict, List, Tuple

VERSION = 5
SIZE = 37
DATA_CODEWORDS = 108
ECC_CODEWORDS = 26
MAX_BYTES = 106
EC_LEVEL_BITS = 0b01
MASK = 0
FORMAT_POLYNOMIAL = 0x537
FORMAT_XOR = 0x5412
RS_POLYNOMIAL = 0x11D


def make_matrix(payload: Dict[str, Any]) -> List[List[bool]]:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ValueError("QR payload too large")

    codewords = _encode_data(data)
    ecc = _rs_remainder(codewords, ECC_CODEWORDS)
    bits: List[int] = []
    for byte in codewords + ecc:
        bits.extend((byte >> shift) & 1 for shift in range(7, -1, -1))
    bits.extend([0] * 7)

    modules = [[False] * SIZE for _ in range(SIZE)]
    function = [[False] * SIZE for _ in range(SIZE)]

    def set_function(x: int, y: int, dark: bool) -> None:
        if 0 <= x < SIZE and 0 <= y < SIZE:
            modules[y][x] = dark
            function[y][x] = True

    for cx, cy in ((3, 3), (SIZE - 4, 3), (3, SIZE - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                distance = max(abs(dx), abs(dy))
                set_function(cx + dx, cy + dy, distance != 2 and distance != 4)

    for index in range(SIZE):
        if not function[6][index]:
            set_function(index, 6, index % 2 == 0)
        if not function[index][6]:
            set_function(6, index, index % 2 == 0)

    for cx, cy in ((30, 30),):
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                distance = max(abs(dx), abs(dy))
                set_function(cx + dx, cy + dy, distance != 1)

    format_bits = _format_bits()
    for index in range(15):
        bit = (format_bits >> index) & 1
        x1, y1 = _format_position_1(index)
        x2, y2 = _format_position_2(index)
        set_function(x1, y1, bool(bit))
        set_function(x2, y2, bool(bit))
    set_function(8, SIZE - 8, True)

    index = 0
    right = SIZE - 1
    upward = True
    while right >= 1:
        if right == 6:
            right = 5
        for step in range(SIZE):
            y = SIZE - 1 - step if upward else step
            for x in (right, right - 1):
                if not function[y][x]:
                    bit = bits[index] if index < len(bits) else 0
                    if (x + y) % 2 == 0:
                        bit ^= 1
                    modules[y][x] = bool(bit)
                    index += 1
        right -= 2
        upward = not upward
    return modules


def _encode_data(data: bytes) -> List[int]:
    bits: List[int] = []
    _append_bits(bits, 0b0100, 4)
    _append_bits(bits, len(data), 8)
    for byte in data:
        _append_bits(bits, byte, 8)
    capacity = DATA_CODEWORDS * 8
    bits.extend([0] * min(4, capacity - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    codewords = [sum(bit << (7 - index) for index, bit in enumerate(bits[offset:offset + 8])) for offset in range(0, len(bits), 8)]
    pad = 0xEC
    while len(codewords) < DATA_CODEWORDS:
        codewords.append(pad)
        pad = 0x11 if pad == 0xEC else 0xEC
    return codewords


def _append_bits(bits: List[int], value: int, count: int) -> None:
    bits.extend((value >> shift) & 1 for shift in range(count - 1, -1, -1))


def _format_bits() -> int:
    value = (EC_LEVEL_BITS << 3) | MASK
    remainder = value << 10
    for shift in range(14, 9, -1):
        if remainder & (1 << shift):
            remainder ^= FORMAT_POLYNOMIAL << (shift - 10)
    return ((value << 10) | remainder) ^ FORMAT_XOR


def _format_position_1(index: int) -> Tuple[int, int]:
    if index < 6:
        return (8, index)
    if index == 6:
        return (8, 7)
    if index == 7:
        return (8, 8)
    if index == 8:
        return (7, 8)
    return (14 - index, 8)


def _format_position_2(index: int) -> Tuple[int, int]:
    if index < 8:
        return (SIZE - 1 - index, 8)
    return (8, SIZE - 15 + index)


def _gf_multiply(x: int, y: int) -> int:
    result = 0
    for shift in range(7, -1, -1):
        result = (result << 1) ^ ((result >> 7) * RS_POLYNOMIAL)
        result ^= ((y >> shift) & 1) * x
    return result


def _rs_generator(degree: int) -> List[int]:
    result = [0] * degree
    result[-1] = 1
    root = 1
    for _ in range(degree):
        for index in range(degree):
            result[index] = _gf_multiply(result[index], root)
            if index + 1 < degree:
                result[index] ^= result[index + 1]
        root = _gf_multiply(root, 2)
    return result


def _rs_remainder(data: List[int], degree: int) -> List[int]:
    generator = _rs_generator(degree)
    result = [0] * degree
    for byte in data:
        factor = byte ^ result[0]
        result.pop(0)
        result.append(0)
        for index in range(degree):
            result[index] ^= _gf_multiply(generator[index], factor)
    return result
