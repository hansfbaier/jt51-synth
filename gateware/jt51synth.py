#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: MIT
import os
from typing import Counter
from luna.gateware import stream

from nmigen              import Elaboratable, Module, Cat, ClockSignal, ResetSignal, DomainRenamer

from luna                import top_level_cli
from luna.usb2           import USBDevice, USBStreamInEndpoint, USBStreamOutEndpoint

from luna.gateware.platform            import NullPin
from luna.gateware.usb.usb2.request    import StallOnlyRequestHandler
from nmigen.lib.fifo import AsyncFIFO

from usb_protocol.types                import USBRequestType, USBDirection
from usb_protocol.emitters             import DeviceDescriptorCollection
from usb_protocol.types.descriptors    import uac
from usb_protocol.emitters.descriptors import uac

from jt51           import Jt51, Jt51Streamer
from adat           import ADATTransmitter, EdgeToPulse
from midicontroller import MIDIController

class JT51Synth(Elaboratable):
    """ JT51 based FPGA synthesizer with USB MIDI """
    MAX_PACKET_SIZE = 512

    def create_descriptors(self):
        """ Creates the descriptors that describe our MIDI topology. """

        descriptors = DeviceDescriptorCollection()

        # Create a device descriptor with our user parameters...
        with descriptors.DeviceDescriptor() as d:
            d.bcdUSB             = 2.00
            d.bDeviceClass       = 0xEF
            d.bDeviceSubclass    = 0x02
            d.bDeviceProtocol    = 0x01
            d.idVendor           = 0x16d0
            d.idProduct          = 0x0f3b

            d.iManufacturer      = "N/A"
            d.iProduct           = "JT51-Synth"
            d.iSerialNumber      = "0001"
            d.bcdDevice          = 0.01

            d.bNumConfigurations = 1

        with descriptors.ConfigurationDescriptor() as configDescr:
            interface = uac.StandardMidiStreamingInterfaceDescriptorEmitter()
            interface.bInterfaceNumber = 0
            interface.bNumEndpoints = 1 # 2
            configDescr.add_subordinate_descriptor(interface)

            streamingInterface = uac.ClassSpecificMidiStreamingInterfaceDescriptorEmitter()

            # prevent the descriptor from getting too large, see https://github.com/greatscottgadgets/luna/issues/86
            #outToHostJack = uac.MidiOutJackDescriptorEmitter()
            #outToHostJack.bJackID = 1
            #outToHostJack.bJackType = uac.MidiStreamingJackTypes.EMBEDDED
            #outToHostJack.add_source(2)
            #streamingInterface.add_subordinate_descriptor(outToHostJack)
#
            #inToDeviceJack = uac.MidiInJackDescriptorEmitter()
            #inToDeviceJack.bJackID = 2
            #inToDeviceJack.bJackType = uac.MidiStreamingJackTypes.EXTERNAL
            #streamingInterface.add_subordinate_descriptor(inToDeviceJack)

            inFromHostJack = uac.MidiInJackDescriptorEmitter()
            inFromHostJack.bJackID = 3
            inFromHostJack.bJackType = uac.MidiStreamingJackTypes.EMBEDDED
            streamingInterface.add_subordinate_descriptor(inFromHostJack)

            outFromDeviceJack = uac.MidiOutJackDescriptorEmitter()
            outFromDeviceJack.bJackID = 4
            outFromDeviceJack.bJackType = uac.MidiStreamingJackTypes.EXTERNAL
            outFromDeviceJack.add_source(3)
            streamingInterface.add_subordinate_descriptor(outFromDeviceJack)

            outEndpoint = uac.StandardMidiStreamingBulkDataEndpointDescriptorEmitter()
            outEndpoint.bEndpointAddress = USBDirection.OUT.to_endpoint_address(1)
            outEndpoint.wMaxPacketSize = self.MAX_PACKET_SIZE
            streamingInterface.add_subordinate_descriptor(outEndpoint)

            outMidiEndpoint = uac.ClassSpecificMidiStreamingBulkDataEndpointDescriptorEmitter()
            outMidiEndpoint.add_associated_jack(3)
            streamingInterface.add_subordinate_descriptor(outMidiEndpoint)

            # prevent the descriptor from getting too large, see https://github.com/greatscottgadgets/luna/issues/86
            #inEndpoint = uac.StandardMidiStreamingDataEndpointDescriptorEmitter()
            #inEndpoint.bEndpointAddress = USBDirection.IN.from_endpoint_address(1)
            #inEndpoint.wMaxPacketSize = self.MAX_PACKET_SIZE
            #streamingInterface.add_subordinate_descriptor(inEndpoint)
#
            #inMidiEndpoint = uac.ClassSpecificMidiStreamingBulkDataEndpointDescriptorEmitter()
            #inMidiEndpoint.add_associated_jack(1)
            #streamingInterface.add_subordinate_descriptor(inMidiEndpoint)

            configDescr.add_subordinate_descriptor(streamingInterface)

        return descriptors

    def elaborate(self, platform):
        m = Module()

        # Generate our domain clocks/resets.
        m.submodules.car = platform.clock_domain_generator()

        # Create our USB-to-serial converter.
        ulpi = platform.request(platform.default_usb_connection)
        m.submodules.usb = usb = USBDevice(bus=ulpi)

        # Add our standard control endpoint to the device.
        descriptors = self.create_descriptors()
        control_ep = usb.add_standard_control_endpoint(descriptors)

        # Attach class-request handlers that stall any vendor or reserved requests,
        # as we don't have or need any.
        stall_condition = lambda setup : \
            (setup.type == USBRequestType.VENDOR) | \
            (setup.type == USBRequestType.RESERVED)
        control_ep.add_request_handler(StallOnlyRequestHandler(stall_condition))

        ep1_out = USBStreamOutEndpoint(
            endpoint_number=1, # EP 1 OUT
            max_packet_size=self.MAX_PACKET_SIZE
        )
        usb.add_endpoint(ep1_out)

        #ep1_in = USBStreamInEndpoint(
        #    endpoint_number=1, # EP 1 IN
        #    max_packet_size=self.MAX_PACKET_SIZE
        #)
        #usb.add_endpoint(ep1_in)

        #counter = Signal(24)
        #m.d.sync += [
        #    counter.eq(counter + 1),
        #    led.eq(counter[20])
        #]

        # Always accept data as it comes in.
        m.d.usb += ep1_out.stream.ready.eq(1)

        # Connect our device as a high speed device
        m.d.comb += [
            usb.connect          .eq(1),
            usb.full_speed_only  .eq(0),
        ]

        m.submodules.midicontroller = midicontroller = MIDIController()
        # connect USB to the MIDIController
        m.d.usb += midicontroller.midi_stream.stream_eq(ep1_out.stream),

        m.submodules.jt51instance = jt51instance = Jt51()
        m.submodules.jt51streamer = jt51streamer = Jt51Streamer(jt51instance)
        m.submodules.sample_valid = sample_valid = DomainRenamer("jt51")(EdgeToPulse())

        adat = platform.request("adat")
        m.submodules.adat_transmitter = adat_transmitter = ADATTransmitter()
        m.submodules.adat_fifo = adat_fifo = AsyncFIFO(width=16+1, depth=32, r_domain="jt51", w_domain="fast")

        # wire up jt51 and ADAT transmitter
        m.d.comb += [
            jt51instance.clk.eq(ClockSignal("jt51")),
            jt51instance.rst.eq(ResetSignal("jt51")),
            jt51instance.cs_n.eq(0),
            jt51streamer.input_stream.stream_eq(midicontroller.jt51_stream),
            sample_valid.edge_in.eq(jt51instance.sample),
            adat.tx.eq(adat_transmitter.adat_out),
        ]

        # this state machine receives the audio from the JT51 and writes it into the ADAT FIFO
        with m.FSM(domain="jt51", name="transmit_fsm"):
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

        # make LEDs blink on incoming MIDI
        leds = Cat(platform.request("led", i) for i in range(8))
        with m.If(ep1_out.stream.valid):
            m.d.usb += [
                leds.eq(ep1_out.stream.payload),
            ]

        return m

if __name__ == "__main__":
    #os.environ["LUNA_PLATFORM"] = "jt51platform:JT51SynthPlatform"
    # use DE0Nano temporarily for testing until I get the USB3320 board
    os.environ["LUNA_PLATFORM"] = "de0nanoplatform:DE0NanoPlatform"
    e = JT51Synth()
    d = e.create_descriptors()
    descriptor_bytes = d.get_descriptor_bytes(2)
    print(f"descriptor length: {len(descriptor_bytes)} bytes: {str(descriptor_bytes.hex())}")
    top_level_cli(JT51Synth)