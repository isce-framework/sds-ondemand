#!/bin/bash

#Copyright 2021, by the California Institute of Technology. ALL RIGHTS RESERVED. United States Government sponsorship acknowledged. Any commercial use must be negotiated with the Office of Technology Transfer at the California Institute of Technology.</font>
#This software may be subject to U.S. export control laws and regulations. By accepting this document, the user agrees to comply with all applicable U.S. export laws and regulations. User has the responsibility to obtain export licenses, or other export authority as may be required, before exporting such information to foreign countries or providing access to foreign persons.<font>

local_base="/home/jovyan/.local"
env_base=${local_base}/envs/mintpy

# (re)create the MintPy/ARIATools environment
conda env create -f env_files/mintpy_conda_env_base.yml -p ${env_base} --force

mintpy_install_dir=${env_base}/tools/MintPy
if [ ! -d ${mintpy_install_dir} ] && echo "Checking out MintPy"
then
   git clone https://github.com/insarlab/MintPy.git ${mintpy_install_dir}
fi

source /opt/conda/bin/activate ${env_base}
sudo yum install -y gcc-c++
pip install kernda

# even if the directory previously exists, this has to be done since the environment is being recreated
pushd ${mintpy_install_dir}
git pull
python -m pip install .
popd

# install/build ARIA-tools
aria_install_dir=${env_base}/tools/ARIA-tools
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
conda env config vars set -n mintpy PATH=${mintpy_install_dir}/mintpy:${aria_install_dir}:${PATH}
conda env config vars set -n mintpy PYTHONPATH=${mintpy_install_dir}:${aria_install_dir}:${PYTHONPATH}
