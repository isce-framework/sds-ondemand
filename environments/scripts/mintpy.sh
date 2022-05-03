#!/bin/bash

#Copyright 2021, by the California Institute of Technology. ALL RIGHTS RESERVED. United States Government sponsorship acknowledged. Any commercial use must be negotiated with the Office of Technology Transfer at the California Institute of Technology.</font>
#This software may be subject to U.S. export control laws and regulations. By accepting this document, the user agrees to comply with all applicable U.S. export laws and regulations. User has the responsibility to obtain export licenses, or other export authority as may be required, before exporting such information to foreign countries or providing access to foreign persons.<font>

source /opt/conda/bin/activate base
pip install kernda
mkdir -p ~/.local/envs
conda config --append envs_dirs ~/.local/envs

local_base="/home/jovyan/.local"
env_base=${local_base}/envs/mintpy

# (re)create the MintPy/ARIATools environment
conda env create -f ../env_files/mintpy_conda_env.yml -p ${env_base} --force

# make the base mintpy files executable
chmod 755 ${env_base}/lib/python*/site-packages/mintpy/*.py

# install/build ARIA-tools
aria_install_dir=${local_base}/tools/ARIA-tools
if [ ! -d ${aria_install_dir} ] && echo "Checking out ARIA-tools"
then
    # add -b <branch/tag> to the following command to install one other than dev
    git clone https://github.com/aria-tools/ARIA-tools ${aria_install_dir}
fi

# even if the directory previously exists, this has to be done since the environment is being recreated
pushd ${aria_install_dir}
git pull
conda run -n mintpy python setup.py build
conda run -n mintpy python setup.py install
popd

# update the ipykernel to recognize the new kernel
conda run -n mintpy python -m ipykernel install --user --name mintpy --display-name "mintpy"
# now invoke kernda to modify the kernel file to ensure the kernel is invoked from within the conda environment
conda run -n mintpy kernda --env-dir ${env_base} --display-name mintpy -o ~/.local/share/jupyter/kernels/mintpy/kernel.json

# Additional ARIA-tools set-up
source /opt/conda/bin/activate ${env_base}
conda env config vars set -n mintpy PATH=${aria_install_dir}:${PATH}
conda env config vars set -n mintpy PYTHONPATH=${aria_install_dir}:${PYTHONPATH}
