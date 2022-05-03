#!/bin/bash

#Copyright 2021, by the California Institute of Technology. ALL RIGHTS RESERVED. United States Government sponsorship acknowledged. Any commercial use must be negotiated with the Office of Technology Transfer at the California Institute of Technology.</font>
#This software may be subject to U.S. export control laws and regulations. By accepting this document, the user agrees to comply with all applicable U.S. export laws and regulations. User has the responsibility to obtain export licenses, or other export authority as may be required, before exporting such information to foreign countries or providing access to foreign persons.<font>

source /opt/conda/bin/activate base
pip install kernda
mkdir -p ~/.local/envs
conda config --append envs_dirs ~/.local/envs

env_base="/home/jovyan/.local/envs/isce"

# (re)create the ISCE2/ISCE3 environment
conda env create -f ../env_files/isce_conda_env.yml -p ${env_base} --force

# update the ipykernel to recognize the new kernel
conda run -n isce python -m ipykernel install --user --name isce --display-name "isce"
# now invoke kernda to modify the kernel file to ensure the kernel is invoked from within the conda environment
conda run -n isce kernda --env-dir ${env_base} --display-name isce -o ~/.local/share/jupyter/kernels/isce/kernel.json

isce_package=${env_base}/lib/python3.10/site-packages/isce

# install the license
tar zxf support_files/stanford_components.tgz -C ${isce_package}

# Additional ISCE set-up
source /opt/conda/bin/activate ${env_base}
conda env config vars set -n isce PATH=${env_base}/bin:${isce_package}/applications:${PATH}
conda env config vars set -n isce PYTHONPATH=${isce_package}:${PYTHONPATH}
