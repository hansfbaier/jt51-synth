#!/usr/bin/env python3
from midicontroller import MIDIController
from nmigen.sim import Simulator, Tick

if __name__ == "__main__":
    dut = MIDIController()
    payload = dut.stream.payload
    valid = dut.stream.valid

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
        yield valid.eq(0)
        yield payload.eq(0)
        yield dut.stream.ready.eq(1)
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
        yield from midi_message(0x90, 0x60, 0x7f)
        yield Tick("usb")
        yield from midi_message(0x80, 0x60, 0x00)
        yield Tick("usb")

    sim = Simulator(dut)
    sim.add_clock(1.0/60e6, domain="usb")
    sim.add_sync_process(usb_process, domain="usb")

    with sim.write_vcd(f'midicontroller.vcd'):
        sim.run()