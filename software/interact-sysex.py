#!/usr/bin/env python3
import sys
import time
from time import sleep
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

def all_patch_fb_test():
    for con in range(8):
        for fb in range(8):
            print("connection: {} feedback: {}".format(con, fb))
            send(0x20, 0b11000000 + con + (fb << 3)); send(0x8, 0x78); sleep(1); send(0x8, 0x0)


note_on = [0x90, 60, 112] # channel 1, middle C, velocity 112
note_off = [0x80, 60, 0]
midiout.send_message(note_on)
time.sleep(0.5)
midiout.send_message(note_off)
time.sleep(0.1)