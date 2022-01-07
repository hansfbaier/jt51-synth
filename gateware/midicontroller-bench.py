#!/usr/bin/env python3
from midicontroller import MIDIController
from amaranth.sim import Simulator, Tick

if __name__ == "__main__":
    dut = MIDIController()
    payload = dut.midi_stream.payload
    valid = dut.midi_stream.valid

    def sysex(*args):
        yield valid.eq(1)
        for byte in args:
            yield payload.eq(byte)
            yield Tick("usb")
        yield payload.eq(0)
        yield valid.eq(0)

    def midi_message(*args, set_valid=True):
        if set_valid:
            yield valid.eq(1)
        yield payload.eq(args[0] >> 4)
        yield Tick("usb")

        for byte in args:
            yield payload.eq(byte)
            yield Tick("usb")

        yield payload.eq(0)
        if set_valid:
            yield valid.eq(0)

    def usb_process():
        for _ in range(2**10 - 200):
            yield Tick("usb")
        yield valid.eq(0)
        yield payload.eq(0)
        yield dut.midi_stream.ready.eq(1)
        yield Tick("usb")
        yield payload.eq(0x0b)
        yield Tick("usb")
        yield Tick("usb")
        yield valid.eq(1)
        yield Tick("usb")
        yield payload.eq(0xb0)
        yield Tick("usb")
        yield payload.eq(0x01)
        yield Tick("usb")
        yield valid.eq(0)
        yield payload.eq(0x00)
        yield Tick("usb")
        yield Tick("usb")
        yield payload.eq(0x0b)
        yield Tick("usb")
        yield Tick("usb")
        yield valid.eq(1)
        yield from midi_message(0xb0, 0x01, 0x03)
        yield valid.eq(0)
        yield Tick("usb")
        yield Tick("usb")
        yield from midi_message(0x93, 69, 0x7f)
        yield Tick("usb")
        yield from midi_message(0x83, 69, 0x00)
        yield Tick("usb")
        yield Tick("usb")
        yield from midi_message(0x93, 60, 0x7f)
        yield from midi_message(0x83, 60, 0x00)
        yield Tick("usb")
        yield Tick("usb")
        yield Tick("usb")
        yield Tick("usb")
        for _ in range(128):
            yield Tick("usb")
        # send USB MIDI sysex
        yield from sysex(0x04, 0xf0, 0x0a, 0x0b, 0x07, 0x0c, 0x0d, 0xf7)
        for _ in range(40):
            yield Tick("usb")
        yield dut.midi_stream.valid.eq(1)
        yield from midi_message(0x93, 60, 0x7f, set_valid=False)
        yield Tick("usb")
        yield from midi_message(0x93, 61, 0x7f, set_valid=False)
        yield dut.midi_stream.valid.eq(0)
        for _ in range(128):
            yield Tick("usb")

    def jt51_process():
        yield Tick("jt51")
        yield Tick("jt51")
        yield Tick("jt51")
        yield Tick("jt51")
        yield dut.jt51_stream.ready.eq(1)
        for _ in range(50):
            yield Tick("jt51")

    sim = Simulator(dut)
    sim.add_clock(1.0/60e6, domain="usb")
    sim.add_clock(1.0/3e6,  domain="jt51")
    sim.add_sync_process(usb_process, domain="usb")
    sim.add_sync_process(jt51_process, domain="jt51")

    with sim.write_vcd(f'midicontroller.vcd'):
        sim.run()
