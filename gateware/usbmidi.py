from amaranth import *
from amaranth.build import Platform

from luna.usb2                      import USBDevice, USBStreamInEndpoint, USBStreamOutEndpoint
from luna.gateware.usb.usb2.request import StallOnlyRequestHandler

from usb_protocol.types                       import USBRequestType, USBDirection
from usb_protocol.emitters                    import DeviceDescriptorCollection
from usb_protocol.emitters.descriptors        import midi1

from amlib.stream                    import StreamInterface

class USBMIDI(Elaboratable):
    def __init__(self, use_ila=False):
        self.stream_out = StreamInterface()
        self._use_ila   = use_ila
        self.additional_endpoints = []

        # USB activity LEDs
        self.usb_tx_active_out      = Signal()
        self.usb_rx_active_out      = Signal()
        self.usb_suspended_out      = Signal()
        self.usb_reset_detected_out = Signal()

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
            interface = midi1.StandardMidiStreamingInterfaceDescriptorEmitter()
            interface.bInterfaceNumber = 0
            interface.bNumEndpoints = 2 if self.with_midi_in else 1
            configDescr.add_subordinate_descriptor(interface)

            streamingInterface = midi1.ClassSpecificMidiStreamingInterfaceDescriptorEmitter()

            if self.with_midi_in:
                outToHostJack = midi1.MidiOutJackDescriptorEmitter()
                outToHostJack.bJackID = 1
                outToHostJack.bJackType = midi1.MidiStreamingJackTypes.EMBEDDED
                outToHostJack.add_source(2)
                streamingInterface.add_subordinate_descriptor(outToHostJack)

                inToDeviceJack = midi1.MidiInJackDescriptorEmitter()
                inToDeviceJack.bJackID = 2
                inToDeviceJack.bJackType = midi1.MidiStreamingJackTypes.EXTERNAL
                streamingInterface.add_subordinate_descriptor(inToDeviceJack)

            inFromHostJack = midi1.MidiInJackDescriptorEmitter()
            inFromHostJack.bJackID = 3
            inFromHostJack.bJackType = midi1.MidiStreamingJackTypes.EMBEDDED
            streamingInterface.add_subordinate_descriptor(inFromHostJack)

            outFromDeviceJack = midi1.MidiOutJackDescriptorEmitter()
            outFromDeviceJack.bJackID = 4
            outFromDeviceJack.bJackType = midi1.MidiStreamingJackTypes.EXTERNAL
            outFromDeviceJack.add_source(3)
            streamingInterface.add_subordinate_descriptor(outFromDeviceJack)

            outEndpoint = midi1.StandardMidiStreamingBulkDataEndpointDescriptorEmitter()
            outEndpoint.bEndpointAddress = USBDirection.OUT.to_endpoint_address(1)
            outEndpoint.wMaxPacketSize = self.MAX_PACKET_SIZE
            streamingInterface.add_subordinate_descriptor(outEndpoint)

            outMidiEndpoint = midi1.ClassSpecificMidiStreamingBulkDataEndpointDescriptorEmitter()
            outMidiEndpoint.add_associated_jack(3)
            streamingInterface.add_subordinate_descriptor(outMidiEndpoint)

            if self.with_midi_in:
                inEndpoint = midi1.StandardMidiStreamingDataEndpointDescriptorEmitter()
                inEndpoint.bEndpointAddress = USBDirection.IN.from_endpoint_address(1)
                inEndpoint.wMaxPacketSize = self.MAX_PACKET_SIZE
                streamingInterface.add_subordinate_descriptor(inEndpoint)

                inMidiEndpoint = midi1.ClassSpecificMidiStreamingBulkDataEndpointDescriptorEmitter()
                inMidiEndpoint.add_associated_jack(1)
                streamingInterface.add_subordinate_descriptor(inMidiEndpoint)

            configDescr.add_subordinate_descriptor(streamingInterface)

            if self._use_ila:
                with configDescr.InterfaceDescriptor() as i:
                    i.bInterfaceNumber = 1

                    with i.EndpointDescriptor() as e:
                        e.bEndpointAddress = USBDirection.IN.to_endpoint_address(3) # EP 3 IN
                        e.wMaxPacketSize   = self.MAX_PACKET_SIZE

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

        for endpoint in self.additional_endpoints:
            usb.add_endpoint(endpoint)

        connect_button = 0 #platform.request("button", 0)
        m.d.comb += [
            usb.connect          .eq(~connect_button),
            # Connect our device as a high speed device
            usb.full_speed_only  .eq(0),
            self.stream_out.stream_eq(ep1_out.stream),
            self.usb_tx_active_out.eq(usb.tx_activity_led),
            self.usb_rx_active_out.eq(usb.rx_activity_led),
            self.usb_suspended_out.eq(usb.suspended),
            self.usb_reset_detected_out.eq(usb.reset_detected),
        ]

        return m
