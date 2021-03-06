from amaranth import *
from amaranth.build import *

from luna.gateware.platform.core import LUNAPlatform

from amaranth_boards.resources import *
from amaranth_boards.qmtech_xc7a35t_core import QMTechXC7A35TPlatform


class JT51SynthClockDomainGenerator(Elaboratable):
    def __init__(self, *, clock_frequencies=None, clock_signal_name=None):
        pass

    def elaborate(self, platform):
        m = Module()

        # Create our domains
        m.domains.fast      = ClockDomain()
        m.domains.sync      = ClockDomain()
        m.domains.usb       = ClockDomain()
        m.domains.usb_shift = ClockDomain()
        m.domains.adat      = ClockDomain()
        m.domains.jt51      = ClockDomain()
        m.domains.jt51int   = ClockDomain()

        fast_clock      = Signal()
        sync_clock      = Signal()
        usb_clock       = Signal()
        usb_shift_clock = Signal()
        adat_clock      = Signal()
        jt51_clock      = Signal()

        mainpll_locked   = Signal()
        mainpll_feedback = Signal()

        adatpll_feedback  = Signal()
        adatpll_locked    = Signal()

        jt51pll_feedback = Signal()
        jt51pll_locked   = Signal()

        clk_50 = platform.request(platform.default_clk)

        m.submodules.mainpll = Instance("PLLE2_ADV",
            p_BANDWIDTH            = "OPTIMIZED",
            p_COMPENSATION         = "ZHOLD",
            p_STARTUP_WAIT         = "FALSE",
            p_DIVCLK_DIVIDE        = 1,
            p_CLKFBOUT_MULT        = 30,
            p_CLKFBOUT_PHASE       = 0.000,
            p_CLKOUT0_DIVIDE       = 25,  # 60MHz
            p_CLKOUT0_PHASE        = 0.000,
            p_CLKOUT0_DUTY_CYCLE   = 0.500,
            p_CLKOUT1_DIVIDE       = 50,  # 30MHz
            p_CLKOUT1_PHASE        = 0.000,
            p_CLKOUT1_DUTY_CYCLE   = 0.500,
            p_CLKIN1_PERIOD        = 20,
            p_CLKOUT2_DIVIDE       = 15,  # 100MHz
            p_CLKOUT2_PHASE        = 0.000,
            p_CLKOUT2_DUTY_CYCLE   = 0.500,
            p_CLKOUT3_DIVIDE       = 25,  # 60MHz
            p_CLKOUT3_PHASE        = 45.000,
            p_CLKOUT3_DUTY_CYCLE   = 0.500,
            p_CLKIN2_PERIOD        = 10,
            i_CLKFBIN              = mainpll_feedback,
            o_CLKFBOUT             = mainpll_feedback,
            i_CLKIN1               = clk_50,
            o_CLKOUT0              = usb_clock,
            o_CLKOUT1              = sync_clock,
            o_CLKOUT2              = fast_clock,
            o_CLKOUT3              = usb_shift_clock,
            o_LOCKED               = mainpll_locked,
        )

        # 12.288MHz = 48kHz * 256
        m.submodules.adat_pll = Instance("MMCME2_ADV",
            p_BANDWIDTH            = "OPTIMIZED",
            p_COMPENSATION         = "ZHOLD",
            p_STARTUP_WAIT         = "FALSE",
            p_DIVCLK_DIVIDE        = 1,
            p_CLKFBOUT_MULT_F      = 17,
            p_CLKFBOUT_PHASE       = 0.000,
            p_CLKOUT0_DIVIDE_F     = 83,  # 12.288MHz = 48kHz * 256
            p_CLKOUT0_PHASE        = 0.000,
            p_CLKOUT0_DUTY_CYCLE   = 0.500,
            p_CLKIN1_PERIOD        = 16.6666666,
            i_CLKFBIN              = adatpll_feedback,
            o_CLKFBOUT             = adatpll_feedback,
            i_CLKIN1               = usb_clock,
            o_CLKOUT0              = adat_clock,
            o_LOCKED               = adatpll_locked,
        )

        # 56 kHz output sample rate is about 2 cents off of A=440Hz
        # but at least we have a frequency a PLL can generate without
        # a dedicated 3.579545 MHz NTSC crystal
        # 3.584 MHz = 56kHz * 64 (1 sample takes 64 JT51 cycles)
        m.submodules.jt51_pll = Instance("MMCME2_ADV",
            p_BANDWIDTH            = "OPTIMIZED",
            p_COMPENSATION         = "ZHOLD",
            p_STARTUP_WAIT         = "FALSE",
            p_DIVCLK_DIVIDE        = 1,
            p_CLKFBOUT_MULT_F      = 27,
            p_CLKFBOUT_PHASE       = 0.000,
            p_CLKOUT6_DIVIDE       = 113,
            p_CLKOUT6_PHASE        = 0.000,
            p_CLKOUT6_DUTY_CYCLE   = 0.500,
            p_CLKOUT4_CASCADE      = "TRUE",
            p_CLKOUT4_DIVIDE       = 2,
            p_CLKOUT4_PHASE        = 0.000,
            p_CLKOUT4_DUTY_CYCLE   = 0.500,
            p_CLKIN1_PERIOD        = 33.3333333,
            i_CLKFBIN              = jt51pll_feedback,
            o_CLKFBOUT             = jt51pll_feedback,
            i_CLKIN1               = sync_clock,
            o_CLKOUT4              = jt51_clock,
            o_LOCKED               = jt51pll_locked,
        )

        locked = Signal()

        # Connect up our clock domains.
        m.d.comb += [
            locked.eq(mainpll_locked & adatpll_locked & jt51pll_locked),
            ClockSignal("fast").eq(fast_clock),
            ClockSignal("sync").eq(sync_clock),
            ClockSignal("usb").eq(usb_clock),
            ClockSignal("usb_shift").eq(usb_shift_clock),
            ClockSignal("adat").eq(adat_clock),
            ClockSignal("jt51").eq(jt51_clock),
            ResetSignal("sync").eq(locked),
            ResetSignal("fast").eq(locked),
            ResetSignal("jt51").eq(locked),
            ResetSignal("adat").eq(locked),
            ResetSignal("sync").eq(locked),
        ]

        return m

class JT51SynthPlatform(QMTechXC7A35TPlatform, LUNAPlatform):
    clock_domain_generator = JT51SynthClockDomainGenerator
    default_usb_connection = "ulpi"
    ulpi_raw_clock_domain  = "usb_shift"

    def toolchain_prepare(self, fragment, name, **kwargs):
        plan = super().toolchain_prepare(fragment, name, **kwargs)
        plan.files['top.xdc'] += """
            set ulpi_out [get_ports -regexp ulpi.*(stp|data).*]
            set_output_delay -clock usb_clk 5 $ulpi_out
            set_output_delay -clock usb_clk -1 -min $ulpi_out
            set ulpi_inputs [get_ports -regexp ulpi.*(data|dir|nxt).*]
            set_input_delay -clock usb_clk -min 1 $ulpi_inputs
            set_input_delay -clock usb_clk -max 3.5 $ulpi_inputs

             # constrain clock domain crossings
            set_max_delay -datapath_only 14 -from [get_cells synthmodule/midicontroller/output_fifo/produce_cdc_produce_w_gry_reg[*]] -to [get_cells synthmodule/midicontroller/output_fifo/produce_cdc/stage0_reg[*]]
            set_max_delay -datapath_only 14 -from [get_cells synthmodule/midicontroller/output_fifo/consume_cdc_consume_r_gry_reg[*]] -to [get_cells synthmodule/midicontroller/output_fifo/consume_cdc/stage0_reg[*]]
            set_max_delay -datapath_only 20 -from [get_cells synthmodule/adat_transmitter/transmit_fifo/produce_cdc_produce_w_gry_reg[*]] -to [get_cells synthmodule/adat_transmitter/transmit_fifo/produce_cdc/stage0_reg[*]]
            set_max_delay -datapath_only 20 -from [get_cells synthmodule/adat_transmitter/transmit_fifo/consume_cdc_consume_r_gry_reg[*]] -to [get_cells synthmodule/adat_transmitter/transmit_fifo/consume_cdc/stage0_reg[*]]
            set_max_delay -datapath_only 20 -from [get_clocks car_jt51_clk] -to [get_clocks car_clk]
            set_max_delay -datapath_only 20 -from [get_clocks car_clk] -to [get_clocks car_jt51_clk]"""

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
                data="J_2:17 J_2:19 J_2:21 J_2:23 J_2:18 J_2:20 J_2:22 J_2:24",
                clk="J_2:7", clk_dir="o", # this needs to be a clock pin of the FPGA or the core won't work
                rst="J_2:8", rst_invert=True, # USB3320 reset is active low
                stp="J_2:9", dir="J_2:11", nxt="J_2:13",
                attrs=Attrs(IOSTANDARD="LVCMOS33")),

            Resource("debug_led", 0, PinsN("J_2:40 J_2:39 J_2:38 J_2:37 J_2:36", dir="o"),
                Attrs(IOSTANDARD="LVCMOS33")),

            Resource("adat", 0,
                Subsignal("tx", Pins("J_1:5", dir="o")),
                Subsignal("rx", Pins("J_1:6", dir="i")),
                Attrs(IOSTANDARD="LVCMOS33"))
        ]

        super().__init__(standalone=False, toolchain=toolchain)
