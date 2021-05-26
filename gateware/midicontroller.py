from nmigen import *
from mido.messages.specs import SPEC_LOOKUP
from luna.gateware.stream import StreamInterface

class MIDIController(Elaboratable):
    def __init__(self, period):
        self.stream = StreamInterface(payload_width=8)
        self.ports = [self.stream]

    def elaborate(self, platform):
        m      = Module()
        stream = self.stream

        msg      = lambda name: SPEC_LOOKUP[name]['status_byte']
        numbytes = lambda name: SPEC_LOOKUP[name]['length']

        status  = Signal(4)
        channel = Signal(4)
        length  = Signal(2)
        message = Array([Signal(8) for _ in range(3)])
        message_index = Signal(2)

        with m.FSM() as fsm:
            with m.State("IDLE"):
                m.d.comb += stream.ready.eq(1)

                # All beginning bytes of MIDI messages have their MSB set
                with m.If(stream.valid & stream.first & stream.payload[7]):
                    m.d.comb += status.eq(stream.payload >> 4)
                    m.d.usb  += [
                        channel.eq(stream.payload & 0xf),
                        message_index.eq(0),
                    ]

                    with m.Switch(status):
                        with m.Case(msg('note-on') >> 4):
                            m.d.usb += length.eq(3)
                            m.next = "NOTE_ON"

                        with m.Case(msg('note-off') >> 4):
                            m.next = "NOTE_OFF"

                        with m.Default():
                            m.next = "WAIT_END"

            with m.State("NOTE_ON"):
                with m.If(stream.valid & stream.first):
                    m.d.usb += [
                        message[message_index].eq(stream.payload),
                        message_index.eq(message_index + 1),
                    ]
                with m.If(message_index == 2):
                    m.next = "IDLE"

            with m.State("NOTE_OFF"):
                pass

            with m.State("WAIT_END"):
                with m.If(stream.vaild & stream.last):
                    m.next = "IDLE"

        return m