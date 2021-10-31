from nmigen import *
from nmigen.build import *

from luna.gateware.platform.core import LUNAPlatform

from nmigen_boards.resources import *
from nmigen_boards.qmtech_ep4ce import QMTechEP4CEPlatform


class JT51SynthClockDomainGenerator(Elaboratable):
    def __init__(self, *, clock_frequencies=None, clock_signal_name=None):
        pass

    def elaborate(self, platform):
        m = Module()

        # Create our domains; but don't do anything else for them, for now.
        m.domains.fast = ClockDomain()
        m.domains.sync = ClockDomain()
        m.domains.usb  = ClockDomain()
        m.domains.jt51 = ClockDomain()
        m.domains.adat = ClockDomain()

        clk = platform.request(platform.default_clk)

        sys_clocks   = Signal(3)
        sound_clocks = Signal(2)

        sys_locked   = Signal()
        sound_locked = Signal()
        reset       = Signal()

        m.submodules.mainpll = Instance("ALTPLL",
            p_BANDWIDTH_TYPE         = "AUTO",
            # 100MHz
            p_CLK0_DIVIDE_BY         = 1,
            p_CLK0_DUTY_CYCLE        = 50,
            p_CLK0_MULTIPLY_BY       = 2,
            p_CLK0_PHASE_SHIFT       = 0,
            # 60MHz
            p_CLK1_DIVIDE_BY         = 5,
            p_CLK1_DUTY_CYCLE        = 50,
            p_CLK1_MULTIPLY_BY       = 6,
            p_CLK1_PHASE_SHIFT       = 0,
            # 30MHz
            p_CLK2_DIVIDE_BY         = 10,
            p_CLK2_DUTY_CYCLE        = 50,
            p_CLK2_MULTIPLY_BY       = 6,
            p_CLK2_PHASE_SHIFT       = 0,

            p_INCLK0_INPUT_FREQUENCY = 20000,
            p_OPERATION_MODE         = "NORMAL",

            # Drive our clock from the USB clock
            # coming from the USB clock pin of the USB3300
            i_inclk  = clk,
            o_clk    = sys_clocks,
            o_locked = sys_locked,
        )

        adat_locked = Signal()
        m.submodules.soundpll = Instance("ALTPLL",
            p_BANDWIDTH_TYPE         = "AUTO",
            # ADAT clock = 12.288 MHz = 48 kHz * 256
            p_CLK0_DIVIDE_BY         = 83,
            p_CLK0_DUTY_CYCLE        = 50,
            p_CLK0_MULTIPLY_BY       = 17,
            p_CLK0_PHASE_SHIFT       = 0,
            # 56 kHz output sample rate is about 2 cents off of A=440Hz
            # but at least we have a frequency a PLL can generate without
            # a dedicated 3.579545 MHz NTSC crystal
            # 3.584 MHz = 56kHz * 64 (1 sample takes 64 JT51 cycles)
            p_CLK1_DIVIDE_BY         = 318,
            p_CLK1_DUTY_CYCLE        = 50,
            p_CLK1_MULTIPLY_BY       = 19,
            p_CLK1_PHASE_SHIFT       = 0,

            p_INCLK0_INPUT_FREQUENCY = 16667,
            p_OPERATION_MODE         = "NORMAL",

            i_inclk  = sys_clocks[1],
            o_clk    = sound_clocks,
            o_locked = sound_locked,
        )

        m.d.comb += [
            reset.eq(~(sys_locked & sound_locked)),
            ClockSignal("fast").eq(sys_clocks[0]),
            ClockSignal("usb") .eq(sys_clocks[1]),
            ClockSignal("sync").eq(sys_clocks[2]),
            ClockSignal("jt51").eq(sound_clocks[1]),
            ClockSignal("adat").eq(sound_clocks[0]),
            ResetSignal("fast").eq(reset),
            ResetSignal("usb") .eq(reset),
            ResetSignal("sync").eq(reset),
            ResetSignal("jt51").eq(reset),
            ResetSignal("adat").eq(reset),
        ]

        ground = platform.request("ground")
        m.d.comb += ground.eq(0)

        return m

class JT51SynthPlatform(QMTechEP4CEPlatform, LUNAPlatform):
    clock_domain_generator = JT51SynthClockDomainGenerator
    default_usb_connection = "ulpi"

    @property
    def file_templates(self):
        templates = super().file_templates
        templates["{{name}}.qsf"] += r"""
            set_global_assignment -name OPTIMIZATION_MODE "Aggressive Performance"
            set_global_assignment -name FITTER_EFFORT "Standard Fit"
            set_global_assignment -name PHYSICAL_SYNTHESIS_EFFORT "Extra"
            set_instance_assignment -name DECREASE_INPUT_DELAY_TO_INPUT_REGISTER OFF -to *ulpi*
            set_instance_assignment -name INCREASE_DELAY_TO_OUTPUT_PIN OFF -to *ulpi*
            set_global_assignment -name NUM_PARALLEL_PROCESSORS ALL
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/filter/jt51_sincf.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/filter/jt51_interpol.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/filter/jt51_fir_ram.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/filter/jt51_fir8.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/filter/jt51_fir4.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/filter/jt51_fir.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/filter/jt51_dac2.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_timers.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_sh.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_reg.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_pm.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_phrom.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_phinc_rom.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_pg.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_op.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_noise_lfsr.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_noise.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_mod.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_mmr.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_lin2exp.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_lfo.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_kon.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_exprom.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_exp2lin.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_eg.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_csr_op.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_csr_ch.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51_acc.v
            set_global_assignment -name VERILOG_FILE ../gateware/jt51/hdl/jt51.v
        """
        templates["{{name}}.sdc"] += r"""
            derive_pll_clocks
            """
# Those don't seem to do any good
#            set_net_delay -from [get_registers synthmodule:synthmodule|audio_fifo_left:audio_fifo_left|storage*] -to [get_registers synthmodule:synthmodule|audio_fifo_left:audio_fifo_left|_*] -max -get_value_from_clock_period dst_clock_period -value_multiplier 0.8
#            set_max_skew -from [get_keepers synthmodule:synthmodule|audio_fifo_left:audio_fifo_left|storage*] -to [get_keepers synthmodule:synthmodule|audio_fifo_left:audio_fifo_left|_*] -get_skew_value_from_clock_period min_clock_period -skew_value_multiplier 0.8
#            set_net_delay -from [get_registers synthmodule:synthmodule|audio_fifo_right:audio_fifo_right|storage*] -to [get_registers synthmodule:synthmodule|audio_fifo_right:audio_fifo_right|_*] -max -get_value_from_clock_period dst_clock_period -value_multiplier 0.8
#            set_max_skew -from [get_keepers synthmodule:synthmodule|audio_fifo_right:audio_fifo_right|storage*] -to [get_keepers synthmodule:synthmodule|audio_fifo_right:audio_fifo_right|_*] -get_skew_value_from_clock_period min_clock_period -skew_value_multiplier 0.8
#            set_net_delay -from [get_registers synthmodule:synthmodule|adat_transmitter:adat_transmitter|transmit_fifo:transmit_fifo|storage*] -to [get_registers synthmodule:synthmodule|adat_transmitter:adat_transmitter|transmit_fifo:transmit_fifo|_*] -max -get_value_from_clock_period dst_clock_period -value_multiplier 0.8
#            set_max_skew -from [get_keepers synthmodule:synthmodule|adat_transmitter:adat_transmitter|transmit_fifo:transmit_fifo|storage*] -to [get_keepers synthmodule:synthmodule|adat_transmitter:adat_transmitter|transmit_fifo:transmit_fifo|_*] -get_skew_value_from_clock_period min_clock_period -skew_value_multiplier 0.8
#        """
        return templates

    def __init__(self):
        self.resources += [
            # USB2 / ULPI section of the USB3300.
            ULPIResource("ulpi", 0,
                data="J_2:31 J_2:29 J_2:27 J_2:25 J_2:23 J_2:21 J_2:19 J_2:17",
                clk="J_2:9", clk_dir="o", # this needs to be a clock pin of the FPGA or the core won't work
                dir="J_2:11", nxt="J_2:13", stp="J_2:15", rst="J_2:7", rst_invert=True, # USB3320 reset is active low
                attrs=Attrs(io_standard="3.3-V LVCMOS")),

            Resource("ground", 0, Pins(" ".join([f"J_2:{i}" for i in range(12, 33, 2)]), dir="o"), Attrs(io_standard="3.3-V LVCMOS")),

            Resource("debug_led", 0, Pins("J_2:34 J_2:36 J_2:38 J_2:40 J_2:42 J_2:44 J_2:46 J_2:48", dir="o"), Attrs(io_standard="3.3-V LVCMOS")),

            #UARTResource(0, rx="J_2:8", tx="J_2:10", attrs=Attrs(io_standard="3.3-V LVCMOS")),

            Resource("adat", 0,
                Subsignal("tx", Pins("J_3:7", dir="o")),
                Subsignal("rx", Pins("J_3:8", dir="i")),
                Attrs(io_standard="3.3-V LVCMOS"))
        ]

        super().__init__(standalone=True)