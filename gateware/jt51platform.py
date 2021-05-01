from nmigen import *
from nmigen.build import *

from luna.gateware.platform.core import LUNAPlatform

from nmigen_boards.resources import *
from nmigen_boards.qmtech_xc7a35t_core import QMTechXC7A35TCorePlatform


class JT51SynthClockDomainGenerator(Elaboratable):
    """ Clock/Reset Controller for the Arty A7. """

    def __init__(self, *, clock_frequencies=None, clock_signal_name=None):
        pass

    def elaborate(self, platform):
        m = Module()

        # Create our domains
        m.domains.sync = ClockDomain()
        m.domains.usb  = ClockDomain()
        m.domains.fast = ClockDomain()

        main_clock = Signal()
        fast_clock = Signal()
        locked = Signal()
        feedback = Signal()

        m.submodules.usb2_pll = Instance("PLLE2_ADV",
            p_BANDWIDTH            = "OPTIMIZED",
            p_COMPENSATION         = "ZHOLD",
            p_STARTUP_WAIT         = "FALSE",
            p_DIVCLK_DIVIDE        = 1,
            p_CLKFBOUT_MULT        = 20,
            p_CLKFBOUT_PHASE       = 0.000,
            p_CLKOUT0_DIVIDE       = 20,
            p_CLKOUT0_PHASE        = 0.000,
            p_CLKOUT0_DUTY_CYCLE   = 0.500,
            p_CLKOUT1_DIVIDE       = 12,
            p_CLKOUT1_PHASE        = 0.000,
            p_CLKOUT1_DUTY_CYCLE   = 0.500,
            p_CLKIN1_PERIOD        = 16.666666,
            i_CLKFBIN              = feedback,
            o_CLKFBOUT             = feedback,
            i_CLKIN1               = ClockSignal("usb"),
            o_CLKOUT0              = main_clock,
            o_CLKOUT1              = fast_clock,
            o_LOCKED               = locked,
        )

        # Connect up our clock domains.
        m.d.comb += [
            ResetSignal("usb") .eq(~locked),
            ClockSignal("sync").eq(main_clock),
            ClockSignal("fast").eq(fast_clock)
        ]

        return m

class JT51SynthPlatform(QMTechXC7A35TCorePlatform, LUNAPlatform):
    clock_domain_generator = JT51SynthClockDomainGenerator
    default_usb_connection = "ulpi"

    def __init__(self):
        self.resources += [
            # USB2 / ULPI section of the USB3300.
            ULPIResource("ulpi", 0,
                data="J_2:15 J_2:16 J_2:17 J_2:18 J_2:19 J_2:20 J_2:21 J_2:22",
                clk="J_2:7", # this needs to be a clock pin of the FPGA or the core won't work
                dir="J_2:9", nxt="J_2:10", stp="J_2:11", rst="J_2:8",
                attrs=Attrs(io_standard="LVCMOS33")
            ),

            UARTResource(0, rx="J_2:6", tx="J_2:5", attrs=Attrs(io_standard="LVCMOS33")),

            Resource("adat", 0,
                Subsignal("tx", Pins("J_3:5", dir="o")),
                Subsignal("rx", Pins("J_3:6", dir="i")))
        ]

        super().__init__(standalone=True)