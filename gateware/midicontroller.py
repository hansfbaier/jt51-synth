#!/usr/bin/env python3
from nmigen import *
from nmigen.cli import main
from mido.messages.specs import SPEC_LOOKUP
from luna.gateware.stream import StreamInterface

midi_to_keycode = {
    1:   0,  # C#
    2:   1,  # D
    3:   2,  # D#
    4:   4,  # E
    5:   5,  # F
    6:   6,  # F#
    7:   8,  # G
    8:   9,  # G#
    9:  10,  # A
    10: 12,  # A#
    11: 13,  # B
    0:  14   # C
}

class MIDIController(Elaboratable):
    def __init__(self):
        self.stream = StreamInterface(payload_width=8)
        self.ports = [self.stream]

    def elaborate(self, platform):
        m      = Module()
        stream = self.stream

        is_status = lambda name: SPEC_LOOKUP[name]['status_byte'] >> 4
        numbytes  = lambda name: SPEC_LOOKUP[name]['length']

        status  = Signal(4)
        channel = Signal(4)
        length  = Signal(2)
        message = Array([Signal(8) for _ in range(3)])
        message_index = Signal(2)

        address = Signal(8)
        data    = Signal(8)

        # USB channel messages come in groups of four bytes:
        # 0S SC DD DD, where S = Status, C = Channel, D = Data
        with m.FSM(domain="usb"):
            with m.State("IDLE"):
                m.d.comb += stream.ready.eq(1)

                # All beginning bytes of MIDI messages have their MSB set
                with m.If(stream.valid):
                    m.d.comb += status.eq(stream.payload)
                    m.d.usb  += message_index.eq(0)

                    with m.Switch(status):
                        with m.Case(is_status('note_on')):
                            m.d.usb += length.eq(numbytes('note_on'))
                            m.next = "NOTE_ON"

                        with m.Case(is_status('note_off')):
                            m.d.usb += length.eq(numbytes('note_off'))
                            m.next = "NOTE_OFF"

                        with m.Case(is_status('control_change')):
                            m.d.usb += length.eq(numbytes('control_change'))
                            m.next = "CONTROL_CHANGE"

                        with m.Case(is_status('pitchwheel')):
                            m.d.usb += length.eq(numbytes('pitchwheel'))
                            m.next = "PITCH_WHEEL"

                        with m.Default():
                            m.next = "WAIT_END"

            with m.State("NOTE_ON"):
                with m.If(stream.valid):
                    m.d.usb += [
                        message[message_index].eq(stream.payload),
                        message_index.eq(message_index + 1),
                        # limit MIDI channels to 0-7
                        address.eq(0x28 + (0xf & (stream.payload & 0b111)))
                    ]

                    with m.If(message_index == 1):
                        with m.Switch(stream.payload):
                            for note in range(21, 109):
                                with m.Case(note):
                                    m.d.usb += data.eq(Cat(Const(midi_to_keycode[note % 12], 4), Const(((note // 12) - 1), 4)))

                            with m.Default():
                                m.d.usb += data.eq(0)

                    with m.If(message_index == 2):
                        m.next = "IDLE"

            with m.State("NOTE_OFF"):
                m.next = "WAIT_END"

            with m.State("CONTROL_CHANGE"):
                m.next = "WAIT_END"

            with m.State("PROGRAM_CHANGE"):
                m.next = "WAIT_END"

            with m.State("PITCH_WHEEL"):
                m.next = "WAIT_END"

            with m.State("WAIT_END"):
                with m.If(~stream.valid):
                    m.next = "IDLE"

        return m


if __name__ == "__main__":
    m = MIDIController()
    main(m, name="midicontroller", ports=[m.stream.valid, m.stream.payload])