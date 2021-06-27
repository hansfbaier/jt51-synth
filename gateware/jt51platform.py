from nmigen import *
from nmigen.build import *

from luna.gateware.platform.core import LUNAPlatform

from nmigen_boards.resources import *
from nmigen_boards.qmtech_xc7a35t_core import QMTechXC7A35TPlatform


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
        m.domains.jt51 = ClockDomain()
        m.domains.adat = ClockDomain()

        main_clock = Signal()
        fast_clock = Signal()
        jt51_clock = Signal()
        adat_clock = Signal()

        locked   = Signal()
        feedback = Signal()

        adat_feedback = Signal()
        adat_locked = Signal()

        clk_50 = platform.request(platform.default_clk)

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
            i_CLKIN1               = clk_50,
            o_CLKOUT0              = main_clock,
            o_CLKOUT1              = fast_clock,
            o_LOCKED               = locked,
        )

        m.submodules.adat_pll = Instance("PLLE2_ADV",
            p_BANDWIDTH            = "OPTIMIZED",
            p_COMPENSATION         = "ZHOLD",
            p_STARTUP_WAIT         = "FALSE",
            p_DIVCLK_DIVIDE        = 1,
            p_CLKFBOUT_MULT        = 29,
            p_CLKFBOUT_PHASE       = 0.000,
            p_CLKOUT0_DIVIDE       = 118,  # 12.288MHz
            p_CLKOUT0_PHASE        = 0.000,
            p_CLKOUT0_DUTY_CYCLE   = 0.500,
            p_CLKIN1_PERIOD        = 20,
            i_CLKFBIN              = adat_feedback,
            o_CLKFBOUT             = adat_feedback,
            i_CLKIN1               = clk_50,
            o_CLKOUT0              = adat_clock,
            o_LOCKED               = adat_locked,
        )

        led = platform.request("led")

        jt51_counter = Signal(6)
        # we need 3.59 MHz for the jt51
        # so we divide 125 MHz by 35
        # error: 125/35/3.59-1 = 0.005173
        m.d.fast += [
            jt51_counter.eq(jt51_counter + 1)
        ]
        with m.If(jt51_counter == 34):
            m.d.fast += [
                jt51_counter.eq(0),
                jt51_clock.eq(1)
            ]
        with m.Elif(jt51_counter == 17):
            m.d.fast += jt51_clock.eq(0)

        # Connect up our clock domains.
        m.d.comb += [
            led.eq(locked),
            ClockSignal("sync").eq(main_clock),
            ClockSignal("usb").eq(main_clock),
            ClockSignal("fast").eq(fast_clock),
            ClockSignal("jt51").eq(jt51_clock),
            ClockSignal("adat").eq(adat_clock),
            ResetSignal("sync").eq(locked & adat_locked),
            ResetSignal("fast").eq(locked & adat_locked),
            ResetSignal("jt51").eq(locked & adat_locked),
            ResetSignal("adat").eq(locked & adat_locked),
            ResetSignal("sync").eq(locked & adat_locked),
        ]

        platform.add_clock_constraint(main_clock, 60e6)

        ground = platform.request("ground")
        m.d.comb += ground.eq(0)

        return m

class JT51SynthPlatform(QMTechXC7A35TPlatform, LUNAPlatform):
    clock_domain_generator = JT51SynthClockDomainGenerator
    default_usb_connection = "ulpi"

    def toolchain_prepare(self, fragment, name, **kwargs):
        plan = super().toolchain_prepare(fragment, name, **kwargs)
        plan.files['top.xdc'] += "\nset ulpi_out [get_ports -regexp ulpi.*(stp|data).*]\n" + \
                                 "set_output_delay -clock main_clock 5 $ulpi_out\n" + \
                                 "set_output_delay -clock main_clock -1 -min $ulpi_out\n" + \
                                 "set ulpi_inputs [get_ports -regexp ulpi.*(data|dir|nxt).*]\n" + \
                                 "set_input_delay -clock main_clock -min 1 $ulpi_inputs\n" + \
                                 "set_input_delay -clock main_clock -max 3.5 $ulpi_inputs\n"

        jt51_files = [
            "../gateware/jt51/hdl/jt51_noise_lfsr.v",
            "../gateware/jt51/hdl/jt51_csr_ch.v",
            "../gateware/jt51/hdl/jt51_phinc_rom.v",
            "../gateware/jt51/hdl/deprecated/jt51_sh2.v",
            "../gateware/jt51/hdl/jt51_phrom.v",
            "../gateware/jt51/hdl/jt51_acc.v",
            "../gateware/jt51/hdl/jt51_exp2lin.v",
            "../gateware/jt51/hdl/jt51_op.v",
            "../gateware/jt51/hdl/jt51_csr_op.v",
            "../gateware/jt51/hdl/jt51_sh.v",
            "../gateware/jt51/hdl/jt51_noise.v",
            "../gateware/jt51/hdl/jt51_mod.v",
            "../gateware/jt51/hdl/jt51_lfo.v",
            "../gateware/jt51/hdl/jt51_mmr.v",
            "../gateware/jt51/hdl/jt51_kon.v",
            "../gateware/jt51/hdl/jt51_lin2exp.v",
            "../gateware/jt51/hdl/jt51_pg.v",
            "../gateware/jt51/hdl/jt51.v",
            "../gateware/jt51/hdl/jt51_eg.v",
            "../gateware/jt51/hdl/jt51_timers.v",
            "../gateware/jt51/hdl/jt51_pm.v",
            "../gateware/jt51/hdl/jt51_exprom.v",
            "../gateware/jt51/hdl/filter/jt51_sincf.v",
            "../gateware/jt51/hdl/filter/jt51_interpol.v",
            "../gateware/jt51/hdl/filter/jt51_fir.v",
            "../gateware/jt51/hdl/filter/jt51_fir_ram.v",
            "../gateware/jt51/hdl/filter/jt51_fir8.v",
            "../gateware/jt51/hdl/filter/jt51_dac2.v",
            "../gateware/jt51/hdl/filter/jt51_fir4.v",
            "../gateware/jt51/hdl/jt51_reg.v",
        ]

        plan.files['top.tcl'] = plan.files['top.tcl'].replace("add_files", "add_files " + " ".join(jt51_files))

        return plan

    def __init__(self, toolchain="Vivado"):
        self.resources += [
            # USB2 / ULPI section of the USB3300.
            ULPIResource("ulpi", 0,
                data="J_2:31 J_2:29 J_2:27 J_2:25 J_2:23 J_2:21 J_2:19 J_2:17",
                clk="J_2:9", clk_dir="o", # this needs to be a clock pin of the FPGA or the core won't work
                dir="J_2:11", nxt="J_2:13", stp="J_2:15", rst="J_2:7", rst_invert=True, # USB3320 reset is active low
                attrs=Attrs(IOSTANDARD="LVCMOS33", SLEW="FAST")),

            Resource("ground", 0, Pins(" ".join([f"J_2:{i}" for i in range(8, 33, 2)]), dir="o"), Attrs(IOSTANDARD="LVCMOS33")),

            Resource("debug_led", 0, Pins("J_2:34", dir="o"), Attrs(IOSTANDARD="LVCMOS33")),
            Resource("debug_led", 1, Pins("J_2:36", dir="o"), Attrs(IOSTANDARD="LVCMOS33")),
            Resource("debug_led", 2, Pins("J_2:38", dir="o"), Attrs(IOSTANDARD="LVCMOS33")),
            Resource("debug_led", 3, Pins("J_2:40", dir="o"), Attrs(IOSTANDARD="LVCMOS33")),
            Resource("debug_led", 4, Pins("J_2:42", dir="o"), Attrs(IOSTANDARD="LVCMOS33")),
            Resource("debug_led", 5, Pins("J_2:44", dir="o"), Attrs(IOSTANDARD="LVCMOS33")),
            Resource("debug_led", 6, Pins("J_2:46", dir="o"), Attrs(IOSTANDARD="LVCMOS33")),
            Resource("debug_led", 7, Pins("J_2:48", dir="o"), Attrs(IOSTANDARD="LVCMOS33")),

            UARTResource(0, rx="J_2:8", tx="J_2:10", attrs=Attrs(IOSTANDARD="LVCMOS33")),

            Resource("adat", 0,
                Subsignal("tx", Pins("J_3:7", dir="o")),
                Subsignal("rx", Pins("J_3:8", dir="i")),
                Attrs(IOSTANDARD="LVCMOS33"))
        ]

        super().__init__(standalone=True, toolchain=toolchain)