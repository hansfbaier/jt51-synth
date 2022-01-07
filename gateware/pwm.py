from amaranth import *
from amaranth.build import Platform

class PWM(Elaboratable):
	def __init__(self, width=8):
		self.width = width
		self.i = Signal(width)
		self.o = Signal()

	def elaborate(self, platform: Platform) -> Module:
		m = Module()

		counter = Signal(self.width)

		m.d.comb += self.o.eq(counter < self.i)
		m.d.sync += counter.eq(counter + 1)

		return m