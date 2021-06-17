from nmigen          import Elaboratable, Module, Cat, ClockSignal, ResetSignal, DomainRenamer, ClockDomain
from nmigen.hdl.ast  import Signal
from nmigen.lib.fifo import AsyncFIFO
from nmigen.cli      import main

from luna.gateware.stream import StreamInterface

from jt51           import Jt51, Jt51Streamer
from adat           import ADATTransmitter, EdgeToPulse
from midicontroller import MIDIController

class SynthModule(Elaboratable):
    """ Main Synth module excluding USB, modularized to facilitate integration testing"""
    def __init__(self) -> None:
       self.midi_stream = StreamInterface(payload_width=8)
       self.adat_out = Signal()

    def elaborate(self, platform):
        m = Module()

        m.submodules.midicontroller = midicontroller = MIDIController()
        # connect USB to the MIDIController
        m.d.usb += midicontroller.midi_stream.stream_eq(self.midi_stream),

        m.submodules.jt51instance = jt51instance = Jt51()
        m.submodules.jt51streamer = jt51streamer = Jt51Streamer(jt51instance)
        m.submodules.sample_valid = sample_valid = DomainRenamer("jt51")(EdgeToPulse())

        m.submodules.adat_transmitter = adat_transmitter = ADATTransmitter()
        m.submodules.adat_fifo = adat_fifo = AsyncFIFO(width=16+1, depth=32, w_domain="jt51", r_domain="sync")

        # wire up jt51 and ADAT transmitter
        m.d.comb += [
            jt51instance.clk.eq(ClockSignal("jt51")),
            jt51instance.rst.eq(ResetSignal("jt51")),
            jt51instance.cs_n.eq(0),
            jt51instance.cen.eq(1),
            jt51streamer.input_stream.stream_eq(midicontroller.jt51_stream),
            sample_valid.edge_in.eq(jt51instance.sample),
            adat_transmitter.user_data_in.eq(0),
            self.adat_out.eq(adat_transmitter.adat_out),
        ]

        # make cen_p1 half the JT51 clock speed
        m.d.jt51 += jt51instance.cen_p1.eq(~jt51instance.cen_p1)

        # this state machine receives the audio from the JT51 and writes it into the ADAT FIFO
        with m.FSM(domain="jt51", name="jt51_to_adat_fifo_fsm"):
            with m.State("IDLE"):
                with m.If(sample_valid.pulse_out & adat_fifo.w_rdy):
                    # FIFO-Layout: sample (Bits 0-15), channel (Bit 16)
                    m.d.jt51 += [
                        adat_fifo.w_data.eq(Cat(jt51instance.xleft, 0)),
                        adat_fifo.w_en.eq(1)
                    ]
                    m.next = "LEFT_SAMPLE"
            with m.State("LEFT_SAMPLE"):
                with m.If(adat_fifo.w_rdy):
                    m.d.jt51 += [
                        adat_fifo.w_data.eq(Cat(jt51instance.xright, 1)),
                        adat_fifo.w_en.eq(1)
                    ]
                    m.next = "RIGHT_SAMPLE"
            with m.State("RIGHT_SAMPLE"):
                m.d.jt51 += [
                    adat_fifo.w_data.eq(0),
                    adat_fifo.w_en.eq(0)
                ]
                m.next = "IDLE"

        # FSM which writes the data from the adat_fifo into the ADAT transmitter
        with m.FSM(name="transmit_fsm"):
            with m.State("IDLE"):
                with m.If(adat_fifo.r_rdy):
                    m.d.sync += adat_fifo.r_en.eq(1)
                    m.next = "TRANSFER"

            with m.State("TRANSFER"):
                m.d.sync += adat_fifo.r_en.eq(0),

                with m.If(adat_transmitter.ready_out):
                    m.d.sync += [
                        adat_transmitter.sample_in.eq(adat_fifo.r_data[:16] << 8),
                        adat_transmitter.addr_in.eq(adat_fifo.r_data[16]),
                        adat_transmitter.last_in.eq(adat_fifo.r_data[16])
                    ]
                    m.next = "IDLE"

        return m

if __name__ == "__main__":
    m = SynthModule()
    main(m, name="synthmodule", ports=[m.midi_stream.valid, m.midi_stream.payload, ClockSignal("adat"), ResetSignal("adat"), m.adat_out])