# -*- Makefile -*-
#
# michael a.g. aïvázis <michael.aivazis@para-sim.com>
# (c) 1998-2024 all rights reserved


# external dependencies
# system tools
sys.prefix := /home/jovyan/.local/envs/qed
sys.lib := ${sys.prefix}/lib
# local installs
usr.prefix := /home/jovyan/.local/envs/qed

# gsl
gsl.version := 2.7
gsl.dir := $(sys.prefix)

# hdf5
hdf5.version := 1.12.1
hdf5.dir := ${sys.prefix}
hdf5.parallel := serial
hdf5.incpath := $(hdf5.dir)/include
hdf5.libpath := $(sys.lib)

# pybind11
pybind11.version := 2.9.2
pybind11.dir = $(sys.prefix)

# python
python.version := @PYTHON_VERSION@
python.dir := $(sys.prefix)

# numpy
numpy.version := 1.22.3
numpy.dir := $(sys.prefix)/lib/python$(python.version)/site-packages/numpy/core

# pyre
pyre.version := 1.11.1
pyre.dir := $(usr.prefix)

# install locations
# this is necessary in order to override {mm} appending the build type to the install prefix
builder.dest.prefix := $(project.prefix)/
# install the python packages straight where they need to go
builder.dest.pyc := $(sys.prefix)/lib/python$(python.version)/site-packages/

# control over the build process
# set the python compiler so we don't depend on the symbolic link, which may not even be there
python3.driver := python$(python.version)


# end of file
