from nmigen              import Elaboratable, Module, Signal, Instance

class jt51(Elaboratable):
    def __init__(self):
        self.rst      = Signal()
        self.clk      = Signal()
        self.cen      = Signal()
        self.cen_p1   = Signal()
        self.cs_n     = Signal()
        self.wr_n     = Signal()
        self.a0       = Signal()
        self.din      = Signal(8)
        self.dout     = Signal(8)
        self.ct1      = Signal()
        self.ct2      = Signal()
        self.irq_n    = Signal()
        self.sample   = Signal()
        self.left     = Signal(16)
        self.right    = Signal(16)
        self.xleft    = Signal(16)
        self.xright   = Signal(16)
        self.dacleft  = Signal(16)
        self.dacright = Signal(16)

        # # #

    def elaborate(self, platform):
        m = Module()
        m.submodules += Instance("jt51",
            i_clk      = self.clk,
            i_rst      = self.rst,
            i_cen      = self.cen,
            i_cen_p1   = self.cen_p1,
            i_cs_n     = self.cs_n,
            i_wr_n     = self.wr_n,
            i_a0       = self.a0,
            i_din      = self.din,
            o_dout     = self.dout,
            o_ct1      = self.ct1,
            o_ct2      = self.ct2,
            o_irq_n    = self.irq_n,
            o_sample   = self.sample,
            o_left     = self.left,
            o_right    = self.right,
            o_xleft    = self.xleft,
            o_xright   = self.xright,
            o_dacleft  = self.dacleft,
            o_dacright = self.dacright,
        )

        return m