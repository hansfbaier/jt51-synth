#!/usr/bin/env python3
import usb
from luna.gateware.usb.devices.ila import USBIntegratedLogicAnalyzerFrontend
from luna.gateware.debug.ila       import ILACoreParameters

VENDOR_ID  = 0x16d0
PRODUCT_ID = 0x0f3b

dev=usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
print(dev)

frontend = USBIntegratedLogicAnalyzerFrontend(ila=ILACoreParameters.unpickle(), idVendor=VENDOR_ID, idProduct=PRODUCT_ID, endpoint_no=3)
frontend.interactive_display()