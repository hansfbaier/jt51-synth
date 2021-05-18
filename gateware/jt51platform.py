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
            p_CLKFBOUT_MULT        = 30,
            p_CLKFBOUT_PHASE       = 0.000,
            p_CLKOUT0_DIVIDE       = 25,  # 60MHz
            p_CLKOUT0_PHASE        = 0.000,
            p_CLKOUT0_DUTY_CYCLE   = 0.500,
            p_CLKOUT1_DIVIDE       = 12,  # 125MHz
            p_CLKOUT1_PHASE        = 0.000,
            p_CLKOUT1_DUTY_CYCLE   = 0.500,
            p_CLKIN1_PERIOD        = 20,
            i_CLKFBIN              = feedback,
            o_CLKFBOUT             = feedback,
            i_CLKIN1               = platform.request(platform.default_clk),
            o_CLKOUT0              = main_clock,
            o_CLKOUT1              = fast_clock,
            o_LOCKED               = locked,
        )

        led = platform.request("led")

        # Connect up our clock domains.
        m.d.comb += [
            led.eq(locked),
            ClockSignal("sync").eq(main_clock),
            ClockSignal("usb").eq(main_clock),
            ClockSignal("fast").eq(fast_clock)
        ]

        return m

class JT51SynthPlatform(QMTechXC7A35TCorePlatform, LUNAPlatform):
    clock_domain_generator = JT51SynthClockDomainGenerator
    default_usb_connection = "ulpi"

    def toolchain_prepare(self, fragment, name, **kwargs):
        plan = super().toolchain_prepare(fragment, name, **kwargs)
        plan.files['top.xdc'] += "set ulpi_out [get_ports -regexp ulpi.*(stp|data).*]\n" + \
                                 "set_output_delay -clock usb_clk 5 $ulpi_out\n" + \
                                 "set_output_delay -clock usb_clk -1 -min $ulpi_out\n" + \
                                 "set ulpi_inputs [get_ports -regexp ulpi.*(data|dir|nxt).*]\n" + \
                                 "set_input_delay -clock usb_clk -min 2 $ulpi_inputs\n" + \
                                 "set_input_delay -clock usb_clk -max 5 $ulpi_inputs\n"

        return plan

    def __init__(self, toolchain="Vivado"):
        self.resources += [
            # USB2 / ULPI section of the USB3300.
            ULPIResource("ulpi", 0,
                data="J_2:28 J_2:26 J_2:24 J_2:22 J_2:20 J_2:18 J_2:16 J_2:14",
                clk="J_2:9", # this needs to be a clock pin of the FPGA or the core won't work
                dir="J_2:17", nxt="J_2:15", stp="J_2:13", rst="J_2:19", clk_dir="o",
                attrs=Attrs(IOSTANDARD="LVCMOS33", SLEW="FAST")),

            Resource("debug_leds", 0, Subsignal("leds", Pins("J_2:34 J_2:36 J_2:38 J_2:40 J_2:42 J_2:44 J_2:46 J_2:48", dir="o")), Attrs(IOSTANDARD="LVCMOS33")),

            UARTResource(0, rx="J_2:8", tx="J_2:10", attrs=Attrs(IOSTANDARD="LVCMOS33")),

            Resource("adat", 0,
                Subsignal("tx", Pins("J_3:7", dir="o")),
                Subsignal("rx", Pins("J_3:8", dir="i")),
                Attrs(IOSTANDARD="LVCMOS33"))
        ]

        super().__init__(standalone=True, toolchain=toolchain)