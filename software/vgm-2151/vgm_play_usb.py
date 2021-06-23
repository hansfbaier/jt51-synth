#!/usr/bin/env python3
import sys
import time
import gzip
import asyncio
import vgm
import rtmidi

midiout = rtmidi.MidiOut()
available_ports = midiout.get_ports()

synthport = [i for i in available_ports if "JT51-Synth" in i]
if not synthport:
    print("JT51-Synth not connected!")
    sys.exit(1)

midiout.open_port(available_ports.index(synthport[0]))

def send(address, data):
     msg = [0xf0, address >> 4, address & 0xf, data >> 4, data & 0xf, 0xf7]
     midiout.send_message(msg)

class USBStreamPlayer(vgm.VGMStreamPlayer):
    async def ym2151_write(self, address, data):
        send(address, data)

    async def wait_seconds(self, duration):
        time.sleep(float(duration))

if __name__ == "__main__":
    arg = sys.argv[1]
    if arg.endswith(".vgz"):
        reader = vgm.VGMStreamReader(gzip.GzipFile(arg, "rb"))
        player = USBStreamPlayer()
        asyncio.run(reader.parse_data(player))
