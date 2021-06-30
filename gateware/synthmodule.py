from nmigen          import Elaboratable, Module, ClockSignal, ResetSignal, DomainRenamer
from nmigen.hdl.ast  import Signal
from nmigen.lib.fifo import AsyncFIFO
from nmigen.cli      import main

from nmigen_library.stream      import StreamInterface
from nmigen_library.stream.fifo import connect_fifo_to_stream

from jt51           import Jt51, Jt51Streamer
from resampler      import FractionalResampler
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
        m.submodules.sample_valid = jt51_sample_valid = DomainRenamer("jt51")(EdgeToPulse())

        m.submodules.audio_fifo_left  = audio_fifo_left  = \
            AsyncFIFO(width=16, depth=8, w_domain="jt51", r_domain="sync")
        m.submodules.audio_fifo_right = audio_fifo_right = \
            AsyncFIFO(width=16, depth=8, w_domain="jt51", r_domain="sync")

        filter_stages = 4
        cutoff_frequency = 20e3
        m.submodules.resampler_left = resampler_left = FractionalResampler(
            input_samplerate=56e3, upsample_factor=6, downsample_factor=7,
            filter_instances=filter_stages, filter_cutoff=cutoff_frequency, bitwidth=16, prescale=4)
        m.submodules.resampler_right = resampler_right = FractionalResampler(
            input_samplerate=56e3, upsample_factor=6, downsample_factor=7,
            filter_instances=filter_stages, filter_cutoff=cutoff_frequency, bitwidth=16, prescale=4)

        #m.submodules.adat_fifo = adat_fifo = SyncFIFO(width=16+1, depth=16)
        m.submodules.adat_transmitter = adat_transmitter = ADATTransmitter()

        # wire up jt51
        m.d.comb += [
            jt51instance.clk.eq(ClockSignal("jt51")),
            jt51instance.rst.eq(ResetSignal("jt51")),
            jt51instance.cs_n.eq(0),
            jt51instance.cen.eq(1),
            jt51streamer.input_stream.stream_eq(midicontroller.jt51_stream),
            jt51_sample_valid.edge_in.eq(jt51instance.sample),
        ]

        # make cen_p1 half the JT51 clock speed
        m.d.jt51 += jt51instance.cen_p1.eq(~jt51instance.cen_p1)

        # receive the audio from the JT51 and write it into the audio FIFOs
        with m.If(jt51_sample_valid.pulse_out):
            with m.If(audio_fifo_left.w_rdy):
                # FIFO-Layout: sample (Bits 0-15), channel (Bit 16)
                m.d.jt51 += [
                    audio_fifo_left.w_data.eq(jt51instance.xleft),
                    audio_fifo_left.w_en.eq(1)
                ]
            with m.If(audio_fifo_right.w_rdy):
                m.d.jt51 += [
                    audio_fifo_right.w_data.eq(jt51instance.xright),
                    audio_fifo_right.w_en.eq(1)
                ]
        with m.Else():
            m.d.jt51 += [
                audio_fifo_left.w_data.eq(0),
                audio_fifo_left.w_en.eq(0),
                audio_fifo_right.w_data.eq(0),
                audio_fifo_right.w_en.eq(0),
            ]

        # resample the audio FIFOs
        connect_fifo_to_stream(m, audio_fifo_left,  resampler_left.signal_in)
        connect_fifo_to_stream(m, audio_fifo_right, resampler_right.signal_in)

        # FSM which writes the data from the adat_fifo into the ADAT transmitter
        with m.FSM(name="transmit_fsm"):
            left_channel  = resampler_left.signal_out
            right_channel = resampler_right.signal_out
            m.d.comb += left_channel.ready.eq(adat_transmitter.ready_out)
            m.d.comb += right_channel.ready.eq(adat_transmitter.ready_out)

            with m.State("IDLE"):
                m.d.sync += [
                    adat_transmitter.valid_in.eq(0),
                    adat_transmitter.last_in.eq(0),
                ]

                with m.If(left_channel.valid & adat_transmitter.ready_out):
                    m.d.sync += [
                        adat_transmitter.valid_in.eq(1),
                        adat_transmitter.sample_in.eq(left_channel.payload[:16] << 8),
                        adat_transmitter.addr_in.eq(0),
                        adat_transmitter.last_in.eq(0),
                    ]
                    m.next = "TRANSFER"
                with m.Else():
                    m.d.sync += adat_transmitter.valid_in.eq(0)

            with m.State("TRANSFER"):
                with m.If(right_channel.valid & adat_transmitter.ready_out):
                    m.d.sync += [
                        adat_transmitter.valid_in.eq(1),
                        adat_transmitter.sample_in.eq(right_channel.payload[:16] << 8),
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
