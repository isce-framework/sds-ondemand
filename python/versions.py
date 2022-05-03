#!/usr/bin/env python

#Copyright 2021, by the California Institute of Technology. ALL RIGHTS RESERVED. United States Government sponsorship acknowledged. Any commercial use must be negotiated with the Office of Technology Transfer at the California Institute of Technology.</font>
#This software may be subject to U.S. export control laws and regulations. By accepting this document, the user agrees to comply with all applicable U.S. export laws and regulations. User has the responsibility to obtain export licenses, or other export authority as may be required, before exporting such information to foreign countries or providing access to foreign persons.<font>

from pip._internal.commands.show import search_packages_info
import logging
import matplotlib
logging.getLogger('matplotlib').setLevel(logging.WARNING)

import isce as isce2
import pybind_isce3
import ARIAtools
import mintpy
import plant

print(f"ISCE2 version: {isce2.__version__}")
try:
    isce3_version = pybind_isce3.__version__
except AttributeError:
    isce3_version = "unknown"
print(f"ISCE3 version: {isce3_version}")
print(f"MintPy version: {mintpy.__version__}")
print(f"PLAnT version: {plant.__version__}")
print(f"ARIAtools version: {list(search_packages_info(['ARIAtools']))[0]['version']}")
