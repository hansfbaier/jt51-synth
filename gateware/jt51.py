from nmigen              import Elaboratable, Module, Signal, Instance, ClockDomain
from luna.gateware.stream import StreamInterface
from nmigen.hdl.ast import ResetSignal

class Jt51Streamer(Elaboratable):
    def __init__(self, jt51) -> None:
        self.input_stream = StreamInterface(payload_width=16)
        self.jt51 = jt51

    def elaborate(self, platform):
        m = Module()
        #m.domains.jt51 = ClockDomain("jt51")
        jt51 = self.jt51

        ready   = Signal()
        valid   = Signal()
        address = Signal(8)
        data    = Signal(8)
        busy    = Signal()

        m.d.comb += [
            self.input_stream.ready.eq(ready),
            valid.eq(self.input_stream.valid),
            busy.eq(jt51.dout[7]),
        ]

        with m.If(valid & ready):
            m.d.jt51 += [
                address.eq(self.input_stream.payload[8:]),
                data.eq(self.input_stream.payload[:8]),
                ready.eq(0), # only read one FIFO entry
            ]

        with m.FSM(domain="jt51"):
            with m.State("IDLE"):
                m.d.jt51 += jt51.wr_n.eq(1)

                with m.If(self.input_stream.valid & ~busy):
                    # read a FIFO entry
                    m.d.jt51 += ready.eq(1)
                    m.next = "WRITE_ADDRESS"

            with m.State("WRITE_ADDRESS"):
                m.d.jt51 += [
                    jt51.a0.eq(0),
                    jt51.din.eq(address),
                    jt51.wr_n.eq(0),
                ]
                m.next = "ADDRESS_DONE"

            with m.State("ADDRESS_DONE"):
                m.d.jt51 += jt51.wr_n.eq(1)
                m.next = "WRITE_DATA"

            with m.State("WRITE_DATA"):
                m.d.jt51 += [
                    jt51.a0.eq(1),
                    jt51.din.eq(data),
                    jt51.wr_n.eq(0),
                ]
                m.next = "IDLE"

        return m

class Jt51(Elaboratable):
    def __init__(self) -> None:
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