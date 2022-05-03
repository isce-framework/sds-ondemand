#!/bin/bash

#Copyright 2021, by the California Institute of Technology. ALL RIGHTS RESERVED. United States Government sponsorship acknowledged. Any commercial use must be negotiated with the Office of Technology Transfer at the California Institute of Technology.</font>
#This software may be subject to U.S. export control laws and regulations. By accepting this document, the user agrees to comply with all applicable U.S. export laws and regulations. User has the responsibility to obtain export licenses, or other export authority as may be required, before exporting such information to foreign countries or providing access to foreign persons.<font>


source /opt/conda/bin/activate base
pip install kernda
mkdir -p ~/.local/envs
conda config --append envs_dirs ~/.local/envs

env_base="/home/jovyan/.local/envs/isce_raider"

# (re)create the ISCE2/ISCE3 environment that includes RAiDER
conda env create -f ../env_files/isce_conda_env.yml -p ${env_base} --force
# for now, have to use a slightly customized raider dependency yml file which specifies the correct version of dem_stitcher
conda env update -f ../env_files/environment_raider.yml -p ${env_base}

# install RAiDER, repo will be checked out into /tmp
pushd /tmp
git clone https://github.com/dbekaert/RAiDER
cd RAiDER
conda run -n isce_raider python setup.py install

# update the ipykernel to recognize the new kernel
conda run -n isce_raider python -m ipykernel install --user --name isce_raider --display-name "isce_raider"
# now invoke kernda to modify the kernel file to ensure the kernel is invoked from within the conda environment
conda run -n isce_raider kernda --env-dir ${env_base} --display-name isce_raider -o ~/.local/share/jupyter/kernels/isce_raider/kernel.json

isce_package=${env_base}/lib/python3.10/site-packages/isce

# install the license
popd
tar zxf support_files/stanford_components.tgz -C ${isce_package}

# Additional ISCE set-up
source /opt/conda/bin/activate ${env_base}
conda env config vars set -n isce_raider PATH=${env_base}/bin:${isce_package}/applications:${PATH}
conda env config vars set -n isce_raider PYTHONPATH=${isce_package}:${PYTHONPATH}
