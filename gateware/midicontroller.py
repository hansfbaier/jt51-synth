#!/usr/bin/env python3
from nmigen import *
from nmigen.lib.fifo import AsyncFIFO
from nmigen.cli import main
from nmigen_library.stream import StreamInterface
from mido.messages.specs import SPEC_LOOKUP

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
        self.midi_stream = StreamInterface(payload_width=8)
        self.jt51_stream = StreamInterface(payload_width=16)

    @staticmethod
    def fifo_write(m, fifo, address, data, *, next_state):
        with m.If(fifo.w_rdy):
            m.d.usb += [
                fifo.w_data.eq(Cat(data, address)),
                fifo.w_en.eq(1),
            ]
            m.next = next_state

        with m.Else():
            m.d.usb += fifo.w_en.eq(0)

    def elaborate(self, platform):
        m = Module()
        midi_stream = self.midi_stream
        output_fifo = AsyncFIFO(width=16, depth=1024, w_domain="usb", r_domain="jt51")
        m.submodules.output_fifo = output_fifo

        m.d.comb += [
            self.jt51_stream.payload.eq(output_fifo.r_data),
            self.jt51_stream.valid.eq(output_fifo.r_rdy),
            output_fifo.r_en.eq(self.jt51_stream.ready),
            midi_stream.ready.eq(output_fifo.w_rdy),
        ]

        is_status = lambda name: SPEC_LOOKUP[name]['status_byte'] >> 4
        numbytes  = lambda name: SPEC_LOOKUP[name]['length']

        status  = Signal(4)
        length  = Signal(2)
        message = Array([Signal(8) for _ in range(3)])
        message_index = Signal(3)

        address = Signal(8)
        data    = Signal(8)

        # USB channel messages come in groups of four bytes:
        # 0S SC DD DD, where S = Status, C = Channel, D = Data
        with m.FSM(domain="usb") as fsm:
            with m.State("INIT"):
                init_counter = Signal(10)
                m.d.usb += init_counter.eq(init_counter + 1)
                with m.If(init_counter[9]):
                    m.next = "INIT_CHANNELS"

            with m.State("INIT_CHANNELS"):
                self.fifo_write(m, output_fifo, 0x20, 0xfa, next_state="INIT_ENVELOPES")

            with m.State("INIT_ENVELOPES"):
                envelope_addr = Signal(8, reset=0x60)
                m.d.usb += envelope_addr.eq(envelope_addr + 8)
                with m.If(envelope_addr <= 0x78):
                    self.fifo_write(m, output_fifo, envelope_addr, Const(0x1f, shape=8), next_state="INIT_ENVELOPES")
                    with m.If(envelope_addr == 0x78):
                        m.d.usb += envelope_addr.eq(0x80)
                with m.Elif(envelope_addr <= 0x98):
                    self.fifo_write(m, output_fifo, envelope_addr, Const(0x1f, shape=8), next_state="INIT_ENVELOPES")
                with m.Else():
                    m.d.usb += output_fifo.w_en.eq(0)
                    m.next = "IDLE"

            with m.State("IDLE"):
                m.d.comb += midi_stream.ready.eq(1)
                m.d.usb += output_fifo.w_en.eq(0)
                m.d.usb += message_index.eq(0)

                # All beginning bytes of MIDI messages have their MSB set
                with m.If(midi_stream.valid):
                    m.d.comb += status.eq(midi_stream.payload)

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

                        with m.Case(0x04):
                            m.next = "SYSEX"

                        with m.Default():
                            m.next = "WAIT_END"

            with m.State("NOTE_ON"):
                with m.If(midi_stream.valid):
                    m.d.usb += [
                        message[message_index].eq(midi_stream.payload),
                        message_index.eq(message_index + 1),
                    ]

                    with m.Switch(message_index):
                        with m.Case(0):
                            # limit MIDI channels to 0-7
                            channel_no = (midi_stream.payload & 0b111)
                            # 0x28 = KEY CODE base address
                            m.d.usb += address.eq(0x28 + channel_no)

                        with m.Case(1):
                            with m.Switch(midi_stream.payload):
                                for note in range(13, 109):
                                    with m.Case(note):
                                        keycode = Const(midi_to_keycode[note % 12], 4)
                                        msb = Const((((note - 1) // 12) - 1), 4)
                                        m.d.usb += data.eq(Cat(keycode, msb))
                                with m.Default():
                                    m.d.usb += data.eq(0)

                        with m.Case(2):
                            self.fifo_write(m, output_fifo, address, data, next_state="NOTE_ON_II")

                        with m.Default():
                            m.next = "WAIT_END"
                with m.Else():
                    m.next = "WAIT_END"

            with m.State("NOTE_ON_II"):
                channel_no = (midi_stream.payload & 0b111)
                # turn all oscillators on
                c2_m2_c1_m1 = 0b1111
                self.fifo_write(m, output_fifo, 0x08, (c2_m2_c1_m1 << 3) | channel_no, next_state="IDLE")

            with m.State("NOTE_OFF"):
                with m.If(midi_stream.valid):
                    m.d.usb += [
                        message[message_index].eq(midi_stream.payload),
                        message_index.eq(message_index + 1),
                    ]

                    with m.Switch(message_index):
                        with m.Case(0):
                            # limit MIDI channels to 0-7
                            m.d.usb += address.eq(0x08)
                            m.d.usb += data.eq(midi_stream.payload & 0b111)
                        with m.Case(1):
                            pass
                        with m.Case(2):
                            self.fifo_write(m, output_fifo, address, data, next_state="IDLE")
                        with m.Default():
                            m.next = "WAIT_END"

            with m.State("CONTROL_CHANGE"):
                m.next = "WAIT_END"

            with m.State("PROGRAM_CHANGE"):
                m.next = "WAIT_END"

            with m.State("PITCH_WHEEL"):
                m.next = "WAIT_END"

            # use sysex to directly send address/data pairs to the JT51
            # first two sysex byte:    address: high nibble, low nibble
            # second two sysex bytes:  data:    high nibble, low nibble
            with m.State("SYSEX"):
                with m.If(midi_stream.valid):
                    m.d.usb += message_index.eq(message_index + 1)

                    with m.Switch(message_index):
                        with m.Case(0):
                            m.next = "SYSEX"
                        with m.Case(1):
                            m.d.usb += address[4:8].eq(midi_stream.payload[0:4])
                        with m.Case(2):
                            m.d.usb += address[0:4].eq(midi_stream.payload[0:4])
                        with m.Case(3):
                            with m.If(midi_stream.payload != 0x07):
                                m.next = "WAIT_END"
                        with m.Case(4):
                            m.d.usb += data[4:8].eq(midi_stream.payload[0:4])
                        with m.Case(5):
                            m.d.usb += data[0:4].eq(midi_stream.payload[0:4])
                        with m.Case(6):
                            with m.If(midi_stream.payload == 0xf7):
                                # after this still comes a 0-byte, which we skip
                                self.fifo_write(m, output_fifo, address, data, next_state="IDLE")
                            with m.Else():
                                m.next = "WAIT_END"
                        with m.Default():
                            m.next = "WAIT_END"

            with m.State("WAIT_END"):
                with m.If(~midi_stream.valid):
                    m.next = "IDLE"

        return m


if __name__ == "__main__":
    m = MIDIController()
    main(m, name="midicontroller", ports=[m.midi_stream.valid, m.midi_stream.payload])