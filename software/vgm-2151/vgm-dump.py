import sys
import gzip
import asyncio
import vgm

lfowaves = {
    0: "SAW",
    1: "SQUARE",
    2: "TRIANGLE",
    3: "NOISE"
}

notes = {
     0: "C#",
     1: "D",
     2: "D#",
     4: "E",
     5: "F",
     6: "F#",
     8: "G",
     9: "G#",
    10: "A",
    12: "A#",
    13: "B",
    14: "C"
}

onoff = {
    0: "OFF",
    1: "ON "
}

class TSVStreamPlayer(vgm.VGMStreamPlayer):
    def __init__(self, file):
        self.file = file

    async def ym2151_write(self, address, data):
        result = ""
        if address == 0x08:
            channel   = data & 0x7
            slot_bits = (data >> 3) & 0xf
            modulator1 =  slot_bits & 0b0001
            carrier1   = (slot_bits & 0b0010) >> 1
            modulator2 = (slot_bits & 0b0100) >> 2
            carrier2   = (slot_bits & 0b1000) >> 3
            result = "KEY SWITCH : CHANNEL {}: CARRIER1: {} MODULATOR1: {} CARRIER2: {} MODULATOR2: {}"\
                        .format(channel, onoff[carrier1], onoff[modulator1], onoff[carrier2], onoff[modulator2])
        elif address == 0x01:
            if (data == 0x02):
                result = "LFO RESET"
            elif data == 0:
                result = "LFO RST OFF"
            else:
                result = "*** TEST MODE: {:02x} ***".format(data)
        elif address == 0x18:
            result = f"LFO FREQ   : {data}"
        elif address == 0x19:
            modulation_type = "PM DEPTH" if data & 0b10000000 > 0 else "AM DEPTH"
            value = data & 0x7f
            result = f"{modulation_type}   : {value}"
        elif address == 0x1b:
            wave = data & 0b11
            result = f"LFO WAVEFRM: {lfowaves[wave]}"
        elif address & 0xf8 == 0x28:
            channel = 0x7 & address
            note = data & 0xf
            octave = (data >> 4) & 0x7
            result = "KEY CODE   : CHANNEL {}: OCTAVE: {} NOTE: {}".format(channel, octave, notes[note])
        elif address & 0b11111000 == 0x20:
            operator = address & 0x7
            rl = data >> 6
            feedback = (data >> 3) & 0x7
            connection = data & 0x7
            result = f"OPERATOR {operator} : CONNECTION: {connection} FEEDBACK: {feedback} (RL): {rl}"
        elif address & 0xf8 == 0x38:
            operator = address & 0b111
            am_sensitivity = 0x3 & data
            pm_sensitivity = 0x7 & (data >> 4)
            result = f"OPERATOR {operator} : PM SENSITIVITY: {pm_sensitivity} AM SENSITIVITY: {am_sensitivity}"
        elif address & 0xf8 == 0x30:
            channel = 0x7 & address
            fraction = (data >> 2) & 0x3f
            result = "KEY FRAC   : channel {}: fraction: {}".format(channel, fraction)
        elif address & 0xe0 == 0x40:
            envelope = address & 0x1f
            detune1 = (data >> 4) & 0x7
            phase_multiply = data & 0xf
            result += "PHASEGEN {:02d}: DETUNE1: {:02d}".format(envelope, detune1)
            result += " PHASE MULTIPLY: {:02d}".format(phase_multiply)
        elif address & 0x60 == 0x60:
            envelope = address & 0x1f
            level = data &  0x7f
            result = "ENVELOPE {:02d}: TOTAL LEVEL : {}".format(envelope, level)
        elif address & 0xe0 == 0x80:
            envelope = address & 0x1f
            keyscaling = data >> 6
            attack_rate = data & 0b11111
            result = "ENVELOPE {:02d}: ".format(envelope)
            if attack_rate > 0:
                result += "ATTACK RATE: {:02d}".format(envelope, attack_rate)
            if keyscaling > 0:
                result += " KEYSCALING: {:02d}".format(envelope, keyscaling)
        elif address & 0xe0 == 0xa0:
            envelope = address & 0x1f
            first_decay_rate = data & 0b11111
            am_sensitivity_en = data >> 7
            result = "ENVELOPE {:02d}: DECAY1 RATE: {:02d}".format(envelope, first_decay_rate)
            result += " AM SENSITIVITY ENABLE: {}".format(am_sensitivity_en)
        elif address & 0xc0 == 0xc0:
            envelope = address & 0x1f
            detune2 = data >> 6
            second_decay_rate = data & 0b11111
            result += "ENVELOPE {:02d}: DECAY2 RATE: {:02d}".format(envelope, second_decay_rate)
            result += " PHASEGEN {:02d}: DETUNE2: {:02d}".format(envelope, detune2)
        elif address & 0xe0 == 0xe0:
            envelope = address & 0x1f
            release_rate = data & 0xf
            decay1_level = (data >> 4) & 0xf
            result = "ENVELOPE {:02d}:".format(envelope)
            if decay1_level > 0:
                result += " DECAY1 LEVEL: {:02d}".format(decay1_level)
            if release_rate > 0:
                result += " RELEASE: {:02d}".format(release_rate)

        result = f"          => {address:02x}: {data:02X}    {result}"

        print("" + result)

    async def wait_seconds(self, duration):
        print(f"({duration*1e6:.0f})")

reader = vgm.VGMStreamReader(gzip.GzipFile("test.vgz", "rb"))
player = TSVStreamPlayer(None)
asyncio.run(reader.parse_data(player))
