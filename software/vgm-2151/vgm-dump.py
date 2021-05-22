import sys
import gzip
import asyncio
import vgm

class TSVStreamPlayer(vgm.VGMStreamPlayer):
    def __init__(self, file):
        self.file = file

    async def ym2151_write(self, address, data):
        result = ""
        if address == 0x08:
            channel = data & 0x7
            sound = (data >> 3) & 0xf
            result = "KEY ON     : channel {}: sound {}".format(channel, sound)
        elif address == 0x01:
            if (data == 0x02):
                result = "LFO RESET"
            elif data == 0:
                result = "LFO RST OFF"
            else:
                result = "*** TEST MODE: {:02x} ***".format(data)
        elif address & 0xf8 == 0x28:
            channel = 0x7 & address
            note = data & 0xf
            octave = (data >> 4) & 0x7
            result = "KEY CODE   : channel {}: octave: {} note: {}".format(channel, octave, note)
        elif address & 0xf8 == 0x30:
            channel = 0x7 & address
            fraction = (data >> 2) & 0x3f
            result = "KEY FRAC    : channel {}: fraction: {}".format(channel, fraction)
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
                result += "KEYSCALING: {:02d}".format(envelope, keyscaling)
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
