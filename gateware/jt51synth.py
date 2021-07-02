#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: MIT
from usbmidi import USBMIDI
import os

from nmigen          import Elaboratable, Module, Signal, Cat
from nmigen.hdl.ast  import ClockSignal, ResetSignal
from luna            import top_level_cli
from synthmodule     import SynthModule

class JT51Synth(Elaboratable):
    """ JT51 based FPGA synthesizer with USB MIDI, TopLevel Module """

    def elaborate(self, platform):
        m = Module()

        # Generate our domain clocks/resets.
        m.submodules.car = platform.clock_domain_generator()

        m.submodules.usbmidi = usbmidi = USBMIDI()
        m.submodules.synthmodule = synthmodule = SynthModule()

        m.d.usb  += synthmodule.midi_stream.stream_eq(usbmidi.stream_out),
        adat = platform.request("adat")
        m.d.comb += adat.tx.eq(synthmodule.adat_out)

        return m

if __name__ == "__main__":
    #os.environ["LUNA_PLATFORM"] = "jt51platform:JT51SynthPlatform"
    os.environ["LUNA_PLATFORM"] = "qmtech_ep4ce15_platform:JT51SynthPlatform"
    # use DE0Nano temporarily for testing until I get the USB3320 board
    #os.environ["LUNA_PLATFORM"] = "de0nanoplatform:DE0NanoPlatform"
    top_level_cli(JT51Synth)
