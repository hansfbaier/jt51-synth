import io
import gzip
import struct
from fractions import Fraction


__all__ = ["VGMStreamPlayer", "VGMStreamReader"]


SAMPLE_RATE = 48000


class VGMStreamPlayer:
    async def sn76489_write(self, data):
        raise NotImplementedError("VGMStream.sn76489_write not implemented")

    async def ym2612_write(self, port, address, data):
        raise NotImplementedError("VGMStream.ym2612_write not implemented")

    async def ym2151_write(self, address, data):
        raise NotImplementedError("VGMStream.ym2151_write not implemented")

    async def ym3526_write(self, address, data):
        raise NotImplementedError("VGMStream.ym3526_write not implemented")

    async def ym3812_write(self, address, data):
        raise NotImplementedError("VGMStream.ym3812_write not implemented")

    async def ymf262_write(self, address, data):
        raise NotImplementedError("VGMStream.ymf262_write not implemented")

    async def wait_seconds(self, delay):
        raise NotImplementedError("VGMStream.wait_seconds not implemented")


class VGMStreamReader:
    @classmethod
    def from_file(cls, file):
        if file.name.endswith(".vgz") or file.name.endswith(".gz"):
            return cls(gzip.GzipFile(fileobj=file))
        else:
            return cls(file)

    def _offset(self):
        return self._input.tell() - self._start

    def _read(self, fmt):
        return struct.unpack(fmt, self._input.read(struct.calcsize(fmt)))

    def _read0(self, fmt):
        return self._read(fmt)[0]

    def __init__(self, stream):
        self._input  = stream
        self._start  = stream.tell()

        # @ 0x00 (Fixed header)
        if self._read0("4s") != b"Vgm ":
            raise ValueError("The input is not a VGM file")
        self.eof_offset    = self._offset() + self._read0("<L")
        self.version       = self._read0("<L")
        self.sn76489_clk   = self._read0("<L")
        self.ym2413_clk    = self._read0("<L")
        self.gd3_offset    = self._offset() + self._read0("<L")
        self.total_samples = self._read0("<L")
        self.total_seconds = Fraction(self.total_samples, SAMPLE_RATE)
        self.loop_offset   = self._offset() + self._read0("<L")
        self.loop_samples  = self._read0("<L")
        self.loop_seconds  = Fraction(self.loop_samples, SAMPLE_RATE)
        # if self._version >= 0x1_01:
        self.rate          = self._read0("<L")
        # if self._version >= 0x1_10:
        self.sn76489_fb    = self._read0("<H")
        self.sn76489_srw   = self._read0("B")
        self.sn76489_flags = self._read0("B")
        self.ym2612_clk    = self._read0("<L")
        self.ym2151_clk    = self._read0("<L")
        # if self._version >= 0x1_50:
        self.data_offset   = self._offset() + (self._read0("<L") or 0x0000000C)
        # if self._version >= 0x1_51:
        self.sega_pcm_clk  = self._read0("<L")
        self.sega_pcm_reg  = self._read0("<L")

        # @0 x40 (Extended header)
        extended_header = self._input.read(self.data_offset - self._offset())
        extended_header = extended_header.ljust(0x100, b"\x00")
        data_input, self._input = self._input, io.BytesIO(extended_header)

        self.rf5c68_clk        = self._read0("<L")
        self.ym2203_clk        = self._read0("<L")
        self.ym2608_clk        = self._read0("<L")
        self.ym2610_clk        = self._read0("<L")
        self.ym3812_clk        = self._read0("<L")
        self.ym3526_clk        = self._read0("<L")
        self.y8950_clk         = self._read0("<L")
        self.ymf262_clk        = self._read0("<L")
        self.ymf278b_clk       = self._read0("<L")
        self.ymf271_clk        = self._read0("<L")
        self.ymz280b_clk       = self._read0("<L")
        self.rf5c164_clk       = self._read0("<L")
        self.pwm_clk           = self._read0("<L")
        self.ay8910_clk        = self._read0("<L")
        self.ay8910_type       = self._read0("B")
        self.ay8910_flags      = self._read0("B")
        self.ym2203_flags      = self._read0("B")
        self.ym2608_flags      = self._read0("B")
        self.volume_mod        = self._read0("B")
        _                      = self._read0("B")
        self.loop_base         = self._read0("B")
        self.loop_modifier     = self._read0("B")
        self.gameboy_dmg_clk   = self._read0("<L")
        self.nes_apu_clk       = self._read0("<L")
        self.multipcm_clk      = self._read0("<L")
        self.upd7759_clk       = self._read0("<L")
        self.okim6258_clk      = self._read0("<L")
        self.okim6258_flags    = self._read0("B")
        self.k054539_flags     = self._read0("B")
        self.c140_chip_type    = self._read0("B")
        _                      = self._read0("B")
        self.okim6295_clk      = self._read0("<L")
        self.k051649_clk       = self._read0("<L")
        self.k054539_clk       = self._read0("<L")
        self.huc6280_clk       = self._read0("<L")
        self.c140_clk          = self._read0("<L")
        self.k053260_clk       = self._read0("<L")
        self.pokey_clk         = self._read0("<L")
        self.qsound_clk        = self._read0("<L")

        self._input = data_input

    def chips(self):
        chips = []
        if self.sn76489_clk     > 0: chips.append("SN76489")
        if self.ym2413_clk      > 0: chips.append("YM2413")
        if self.ym2612_clk      > 0: chips.append("YM2612")
        if self.ym2151_clk      > 0: chips.append("YM2151")
        if self.sega_pcm_clk    > 0: chips.append("Sega PCM")
        if self.rf5c68_clk      > 0: chips.append("RF5C68")
        if self.ym2203_clk      > 0: chips.append("YM2203")
        if self.ym2608_clk      > 0: chips.append("YM2608")
        if self.ym2610_clk      > 0: chips.append("YM2610/B")
        if self.ym3812_clk      > 0: chips.append("YM3812")
        if self.ym3526_clk      > 0: chips.append("YM3526")
        if self.y8950_clk       > 0: chips.append("Y8950")
        if self.ymf262_clk      > 0: chips.append("YMF262")
        if self.ymf278b_clk     > 0: chips.append("YMF278B")
        if self.ymf271_clk      > 0: chips.append("YMF271")
        if self.ymz280b_clk     > 0: chips.append("YMZ280B")
        if self.rf5c164_clk     > 0: chips.append("RF5C164")
        if self.pwm_clk         > 0: chips.append("PWM")
        if self.ay8910_clk      > 0: chips.append("AY8910")
        if self.gameboy_dmg_clk > 0: chips.append("GameBoy DMG")
        if self.nes_apu_clk     > 0: chips.append("NES APU")
        if self.multipcm_clk    > 0: chips.append("MultiPCM")
        if self.upd7759_clk     > 0: chips.append("uPD7759")
        if self.okim6258_clk    > 0: chips.append("OKIM6258")
        if self.okim6295_clk    > 0: chips.append("OKIM6295")
        if self.k051649_clk     > 0: chips.append("K051649")
        if self.k054539_clk     > 0: chips.append("K054539")
        if self.huc6280_clk     > 0: chips.append("HuC6280")
        if self.c140_clk        > 0: chips.append("C140")
        if self.k053260_clk     > 0: chips.append("K053260")
        if self.pokey_clk       > 0: chips.append("Pokey")
        if self.qsound_clk      > 0: chips.append("QSound")
        return chips

    async def parse_data(self, player):
        while True:
            command = self._read0("B")
            if command == 0x50:
                await player.sn76489_write(self._read0("B"))
            elif command == 0x52:
                await player.ym2612_write(0,*self._read("BB"))
            elif command == 0x53:
                await player.ym2612_write(1, *self._read("BB"))
            elif command == 0x54:
                await player.ym2151_write(*self._read("BB"))
            elif command == 0x5A:
                await player.ym3812_write(*self._read("BB"))
            elif command == 0x5B:
                await player.ym3526_write(*self._read("BB"))
            elif command in (0x5E, 0x5F):
                address, data = self._read("BB")
                await player.ymf262_write(address|((command & 1) << 8), data)
            elif command == 0x61:
                samples = self._read0("<H")
                await player.wait_seconds(Fraction(samples, SAMPLE_RATE))
            elif command == 0x62:
                samples = 735
                await player.wait_seconds(Fraction(samples, SAMPLE_RATE))
            elif command == 0x63:
                samples = 882
                await player.wait_seconds(Fraction(samples, SAMPLE_RATE))
            elif command == 0x66:
                break
            elif command == 0x67:
                b = self._read("B")
                if b == 0x66:
                    print(f"second byte should be 0x66 in a data block, but was: {b:02x}")
                compression_type = self._read0("B")
                size = self._read0("I")
                print(f"======================== got data block of type 0x{compression_type:02x}  and size {size} ======================== ")
                if compression_type & 0b11000000 == 0x80:
                    datasize = self._read0("I")
                    address = self._read0("I")
                    print(f"ROM/RAM Image dump at address: 0x{address:08x} size: 0x{datasize:08x}")
                    size -= 8
                data = ""
                for i in range(size):
                    databyte = self._read0("B")
                    data += f"{databyte:02x} "
                    if i % 16 == 15:
                        data +="\n"
                print(data)
            elif command in range(0x70, 0x80):
                samples = (command & 0xf) + 1
                await player.wait_seconds(Fraction(samples, SAMPLE_RATE))
            elif command == 0xc0:
                addr_lsb = self._read0("B")
                addr_msb = self._read0("B")
                addr = addr_msb << 8 | addr_lsb
                databyte = self._read0("B")
                print(f"SEGA PCM write to {addr:04x}: {databyte:02x}")
            elif command == 0x90:
                stream_id = self._read0("B")
                chip_type = self._read0("B")
                register  = self._read0("B")
                port      = self._read0("B")
                print(f"Setup Stream Control stream_id: {stream_id:02x} chip type {chip_type:02x} port {port:02x} register {register:02x}")
            elif command == 0x91:
                stream_id = self._read0("B")
                bank_id   = self._read0("B")
                step_size = self._read0("B")
                step_base = self._read0("B")
                print(f"Set Stream Data stream_id: {stream_id:02x} bank {bank_id:02x} step size {step_size:02x} base {step_base:02x}")
            elif command == 0x92:
                stream_id = self._read0("B")
                freq = self._read0("I")
                print(f"Set Stream Frequency stream_id: {stream_id:02x} freq: {freq}")
            elif command == 0x95:
                stream_id = self._read0("B")
                block_id = self._read0("H")
                flags = self._read0("B")
                print(f"Start Stream stream_id: {stream_id:02x}, block id {block_id:04x}, flags {flags:02x}")
            elif command == 0x94:
                stream_id = self._read0("B")
                print(f"Stop Stream stream_id: {stream_id:02x}")
            else:
                raise NotImplementedError("Unknown VGM command {:#04x} at stream offset {}"
                                          .format(command, self._input.tell() - 1))
