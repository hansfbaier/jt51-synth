rm -rf obj_dir
verilator -Wno-fatal --trace --trace-fst --cc --exe  synthmodule.v $(find ../jt51/hdl/ -name \*.v) main.cpp
cd obj_dir
make -j8 -f Vsynthmodule.mk && ./Vsynthmodule