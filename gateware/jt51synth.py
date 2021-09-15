#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: MIT
import os

from nmigen          import Elaboratable, Module, Signal, ClockSignal
from luna            import top_level_cli

from usbmidi         import USBMIDI
from synthmodule     import SynthModule

from luna.gateware.debug.ila import StreamILA, ILACoreParameters
from luna.gateware.usb.usb2.endpoints.stream  import USBMultibyteStreamInEndpoint

class JT51Synth(Elaboratable):
    """ JT51 based FPGA synthesizer with USB MIDI, TopLevel Module """

    USE_ILA = True

    def elaborate(self, platform):
        m = Module()

        # Generate our domain clocks/resets.
        m.submodules.car         = platform.clock_domain_generator()
        m.submodules.usbmidi     = usbmidi = USBMIDI(use_ila=self.USE_ILA)
        m.submodules.synthmodule = synthmodule = SynthModule()

        m.d.comb += synthmodule.midi_stream.stream_eq(usbmidi.stream_out),

        adat = platform.request("adat")
        m.d.comb += adat.tx.eq(synthmodule.adat_out)

        if self.USE_ILA:
            adat_clock = Signal()
            m.d.comb += adat_clock.eq(ClockSignal("adat"))

            usb_valid = Signal()
            usb_ready = Signal()
            usb_payload = Signal()

            m.d.comb += [
                usb_valid.eq (usbmidi.stream_out.valid),
                usb_ready.eq (usbmidi.stream_out.ready),
                usb_payload.eq(usbmidi.stream_out.payload),
            ]

            signals = [
                usb_valid,
                usb_ready,
                usb_payload,
            ]

            signals_bits = sum([s.width for s in signals])
            depth = int(20*8*1024/signals_bits)
            m.submodules.ila = ila = \
                StreamILA(
                    signals=signals,
                    sample_depth=depth,
                    domain="usb", o_domain="usb",
                    samples_pretrigger=256)

            ila_endpoint = USBMultibyteStreamInEndpoint(
                endpoint_number=3, # EP 3 IN
                max_packet_size=usbmidi.MAX_PACKET_SIZE,
                byte_width=ila.bytes_per_sample
            )

            usbmidi.additional_endpoints.append(ila_endpoint)

            m.d.comb += [
                ila_endpoint.stream.stream_eq(ila.stream),
                ila.trigger.eq(usb_ready & usb_valid),
            ]

            ILACoreParameters(ila).pickle()

        return m

if __name__ == "__main__":
    os.environ["LUNA_PLATFORM"] = "qmtech_xc7a35t_platform:JT51SynthPlatform"
    #os.environ["LUNA_PLATFORM"] = "qmtech_ep4ce15_platform:JT51SynthPlatform"
    # use DE0Nano temporarily for testing until I get the USB3320 board
    #os.environ["LUNA_PLATFORM"] = "de0nanoplatform:DE0NanoPlatform"
    top_level_cli(JT51Synth)
