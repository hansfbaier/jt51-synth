#include <verilated.h>
#include <iostream>
#include "Vsynthmodule.h"
#include "verilated_fst_c.h"

Vsynthmodule *top;                      // Instantiation of module

vluint64_t main_time = 0;       // Current simulation time
// This is a 64-bit integer to reduce wrap over issues and
// allow modulus.  This is in units of the timeprecision
// used in Verilog (or from --timescale-override)

const int usb_period  = 16,
          adat_period = 81,
          jt51_period = 279;

double sc_time_stamp() {        // Called by $time in Verilog
    return main_time;           // converts to double, to match
                                // what SystemC does
}

bool send_midi(uint32_t num_cycles, const uint8_t *msg, vluint64_t time)
{
    vluint64_t first_msg_time = num_cycles * usb_period;
    if (time < first_msg_time || time >= first_msg_time + 5 * usb_period) return false;
    if (time == first_msg_time) {
        top->payload = msg[0] >> 4;
        top->valid = 1;
        return true;
    } else if (time == first_msg_time + 1 * usb_period) {
        top->payload = msg[0];
        return true;
    } else if (time == first_msg_time + 2 * usb_period) {
        top->payload = msg[1];
        return true;
    } else if (time == first_msg_time + 3 * usb_period) {
        top->payload = msg[2];
        return true;
    } else if (time == first_msg_time + 4 * usb_period) {
        top->payload = 0;
        top->valid = 0;
        return true;
    }
    return false;
}

const uint8_t note_on[3]  = { 0x93, 0x70 /* 69 */, 0x7f },
              note_off[3] = { 0x83, 0x70 /* 69 */, 0x00 };

bool completed_changed(uint8_t completed)
{
    static uint8_t last_completed = 0xff;

    bool result = completed != last_completed;
    last_completed = completed;
    return result;
}


int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    top = new Vsynthmodule;

    Verilated::traceEverOn(true);
    VL_PRINTF("Enabling waves...\n");
    VerilatedFstC* tfp = new VerilatedFstC;
    top->trace (tfp, 99);	// Trace 99 levels of hierarchy
    tfp->open ("synthmodule.fst");

    VL_PRINTF("Verilating...\n");

    top->usb_rst  = 1;
    top->adat_rst = 1;
    top->jt51_rst = 1;
    top->synthmodule__02Erst = 1;
    top->eval();

    const vluint64_t max_time = 3000000;

    while (main_time < max_time) {
        bool needs_eval = false;
        if (main_time > 10)                             { top->usb_rst = 0; top->adat_rst = 0; top->jt51_rst = 0; top->synthmodule__02Erst = 0; needs_eval = true; }
        if ((main_time % usb_period) == 0)              { top->usb_clk = 1; top->synthmodule__02Eclk = 1; needs_eval = true; }
        if ((main_time % usb_period) == usb_period/2)   { top->usb_clk = 0; top->synthmodule__02Eclk = 0; needs_eval = true; }
        if ((main_time % adat_period) == 0)             { top->adat_clk = 1; needs_eval = true; }
        if ((main_time % adat_period) == adat_period/2) { top->adat_clk = 0; needs_eval = true; }
        if ((main_time % jt51_period) == 0)             { top->jt51_clk = 1; needs_eval = true; }
        if ((main_time % jt51_period) == jt51_period/2) { top->jt51_clk = 0; needs_eval = true; }

        needs_eval |= send_midi(10 * jt51_period, note_on, main_time);
        needs_eval |= send_midi(max_time / 4 * 3 / usb_period, note_off, main_time);

        if (needs_eval) {
            top->eval();
            if (tfp) tfp->dump (main_time);

            uint8_t completed = uint8_t (main_time * 100 / max_time);
            if (completed_changed(completed)) {
                VL_PRINTF("%d%% ", completed);
                fflush(stdout);
            }
        }

        main_time++;
    }

    if (tfp) tfp->close();
    top->final();
    VL_PRINTF("\ndone!\n");

    delete top;
}