from nmigen import *
from nmigen.build import Platform

from luna.usb2                      import USBDevice, USBStreamInEndpoint, USBStreamOutEndpoint
from luna.gateware.usb.usb2.request import StallOnlyRequestHandler

from usb_protocol.types                import USBRequestType, USBDirection
from usb_protocol.emitters             import DeviceDescriptorCollection
from usb_protocol.types.descriptors    import uac
from usb_protocol.emitters.descriptors import uac

from nmigen_library.stream import StreamInterface

class USBMIDI(Elaboratable):
    def __init__(self):
        self.stream_out = StreamInterface()

    MAX_PACKET_SIZE = 512
    # we currently do not need MIDI feedback from the synth
    with_midi_in = False

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
            interface.bNumEndpoints = 2 if self.with_midi_in else 1
            configDescr.add_subordinate_descriptor(interface)

            streamingInterface = uac.ClassSpecificMidiStreamingInterfaceDescriptorEmitter()

            if self.with_midi_in:
                outToHostJack = uac.MidiOutJackDescriptorEmitter()
                outToHostJack.bJackID = 1
                outToHostJack.bJackType = uac.MidiStreamingJackTypes.EMBEDDED
                outToHostJack.add_source(2)
                streamingInterface.add_subordinate_descriptor(outToHostJack)

                inToDeviceJack = uac.MidiInJackDescriptorEmitter()
                inToDeviceJack.bJackID = 2
                inToDeviceJack.bJackType = uac.MidiStreamingJackTypes.EXTERNAL
                streamingInterface.add_subordinate_descriptor(inToDeviceJack)

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

            if self.with_midi_in:
                inEndpoint = uac.StandardMidiStreamingDataEndpointDescriptorEmitter()
                inEndpoint.bEndpointAddress = USBDirection.IN.from_endpoint_address(1)
                inEndpoint.wMaxPacketSize = self.MAX_PACKET_SIZE
                streamingInterface.add_subordinate_descriptor(inEndpoint)

                inMidiEndpoint = uac.ClassSpecificMidiStreamingBulkDataEndpointDescriptorEmitter()
                inMidiEndpoint.add_associated_jack(1)
                streamingInterface.add_subordinate_descriptor(inMidiEndpoint)

            configDescr.add_subordinate_descriptor(streamingInterface)

        return descriptors

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

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
            max_packet_size=self.MAX_PACKET_SIZE)
        usb.add_endpoint(ep1_out)

        if self.with_midi_in:
            ep1_in = USBStreamInEndpoint(
                endpoint_number=1, # EP 1 IN
                max_packet_size=self.MAX_PACKET_SIZE)
            usb.add_endpoint(ep1_in)

        connect_button = 0 #platform.request("button", 0)
        # Connect our device as a high speed device
        m.d.comb += [
            usb.connect          .eq(~connect_button),
            usb.full_speed_only  .eq(0),
        ]

        return m