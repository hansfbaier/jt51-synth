from nmigen          import Elaboratable, Module, ClockSignal, ResetSignal, DomainRenamer
from nmigen.hdl.ast  import Signal
from nmigen.lib.fifo import AsyncFIFO
from nmigen.cli      import main

from nmigen_library.stream      import StreamInterface
from nmigen_library.stream.fifo import connect_stream_to_fifo

from jt51           import Jt51, Jt51Streamer
from resampler      import FractionalResampler
from adat           import ADATTransmitter, EdgeToPulse
from midicontroller import MIDIController

class SynthModule(Elaboratable):
    """ Main Synth module excluding USB, modularized to facilitate integration testing"""
    def __init__(self) -> None:
       self.midi_stream = StreamInterface(payload_width=8)
       self.adat_out    = Signal()

    def elaborate(self, platform):
        m = Module()

        #
        # Set up submodules
        #
        m.submodules.midicontroller = midicontroller = MIDIController()
        # connect USB to the MIDIController
        m.d.usb += midicontroller.midi_stream.stream_eq(self.midi_stream),

        m.submodules.jt51instance = jt51instance = Jt51()
        m.submodules.jt51streamer = jt51streamer = Jt51Streamer(jt51instance)

        bitwidth = 16
        cutoff_frequency = 20e3
        verbose = False
        m.submodules.resampler_left = resampler_left = DomainRenamer("jt51")(FractionalResampler(
            input_samplerate=56e3, upsample_factor=6, downsample_factor=7, filter_order=24,
            filter_cutoff=cutoff_frequency, bitwidth=bitwidth, prescale=4, verbose=verbose))
        m.submodules.resampler_right = resampler_right = DomainRenamer("jt51")(FractionalResampler(
            input_samplerate=56e3, upsample_factor=6, downsample_factor=7, filter_order=24,
            filter_cutoff=cutoff_frequency, bitwidth=bitwidth, prescale=4, verbose=verbose))

        m.submodules.audio_fifo_left  = audio_fifo_left  = \
            AsyncFIFO(width=bitwidth, depth=8, w_domain="jt51", r_domain="sync")
        m.submodules.audio_fifo_right = audio_fifo_right = \
            AsyncFIFO(width=bitwidth, depth=8, w_domain="jt51", r_domain="sync")

        m.submodules.adat_transmitter = adat_transmitter = ADATTransmitter()

        # wire up jt51
        m.d.comb += [
            jt51instance.clk.eq(ClockSignal("jt51")),
            jt51instance.rst.eq(ResetSignal("jt51")),
            jt51instance.cs_n.eq(0),
            jt51instance.cen.eq(1),
            jt51streamer.input_stream.stream_eq(midicontroller.jt51_stream),
        ]

        # make cen_p1 half the JT51 clock speed
        m.d.jt51 += jt51instance.cen_p1.eq(~jt51instance.cen_p1)

        # receive the audio from the JT51 and write it into the resamplers
        with m.If(jt51instance.sample):
            with m.If(resampler_left.signal_in.ready):
                m.d.jt51 += [
                    resampler_left.signal_in.payload.eq(jt51instance.xleft),
                    resampler_left.signal_in.valid.eq(1)
                ]
            with m.If(resampler_right.signal_in.ready):
                m.d.jt51 += [
                    resampler_right.signal_in.payload.eq(jt51instance.xright),
                    resampler_right.signal_in.valid.eq(1)
                ]
        with m.Else():
            m.d.jt51 += [
                resampler_left.signal_in.payload.eq(0),
                resampler_left.signal_in.valid.eq(0),
                resampler_right.signal_in.payload.eq(0),
                resampler_right.signal_in.valid.eq(0),
            ]

        # resample the audio FIFOs
        m.d.comb += [
            connect_stream_to_fifo(resampler_left.signal_out,  audio_fifo_left),
            connect_stream_to_fifo(resampler_right.signal_out, audio_fifo_right),
        ]

        # FSM which writes the data from the FIFOs into the ADAT transmitter
        with m.FSM(name="transmit_fsm"):
            m.d.comb += audio_fifo_left.r_en.eq(adat_transmitter.ready_out)
            m.d.comb += audio_fifo_right.r_en.eq(adat_transmitter.ready_out)

            with m.State("IDLE"):
                m.d.sync += [
                    adat_transmitter.valid_in.eq(0),
                    adat_transmitter.last_in.eq(0),
                ]

                with m.If(audio_fifo_left.r_rdy & adat_transmitter.ready_out):
                    m.d.sync += [
                        adat_transmitter.valid_in.eq(1),
                        adat_transmitter.sample_in.eq(audio_fifo_left.r_data << 8),
                        adat_transmitter.addr_in.eq(0),
                        adat_transmitter.last_in.eq(0),
                    ]
                    m.next = "TRANSFER"
                with m.Else():
                    m.d.sync += adat_transmitter.valid_in.eq(0)

            with m.State("TRANSFER"):
                with m.If(audio_fifo_right.r_rdy & adat_transmitter.ready_out):
                    m.d.sync += [
                        adat_transmitter.valid_in.eq(1),
                        adat_transmitter.sample_in.eq(audio_fifo_right.r_data << 8),
                        adat_transmitter.addr_in.eq(1),
                        adat_transmitter.last_in.eq(1)
                    ]
                    m.next = "IDLE"
                with m.Else():
                    m.d.sync += adat_transmitter.valid_in.eq(0),

        # wire up ADAT transmitter
        m.d.comb += [
            adat_transmitter.user_data_in.eq(0),
            self.adat_out.eq(adat_transmitter.adat_out),
        ]

        return m

if __name__ == "__main__":
    m = SynthModule()
    main(m, name="synthmodule", ports=[m.midi_stream.valid, m.midi_stream.payload, ClockSignal("adat"), ResetSignal("adat"), m.adat_out])
