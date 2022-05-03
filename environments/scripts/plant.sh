#!/bin/bash

#Copyright 2021, by the California Institute of Technology. ALL RIGHTS RESERVED. United States Government sponsorship acknowledged. Any commercial use must be negotiated with the Office of Technology Transfer at the California Institute of Technology.</font>
#This software may be subject to U.S. export control laws and regulations. By accepting this document, the user agrees to comply with all applicable U.S. export laws and regulations. User has the responsibility to obtain export licenses, or other export authority as may be required, before exporting such information to foreign countries or providing access to foreign persons.<font>

source /opt/conda/bin/activate base
pip install kernda
mkdir -p ~/.local/envs
conda config --append envs_dirs ~/.local/envs

env_base="/home/jovyan/.local/envs/plant"

# (re)create the PLAnT environment
conda env create -f ../env_files/plant_conda_env.yml -p ${env_base} --force

# update the ipykernel to recognize the new kernel
conda run -n plant python -m ipykernel install --user --name plant --display-name "plant"
# now invoke kernda to modify the kernel file to ensure the kernel is invoked from within the conda environment
conda run -n plant kernda --env-dir ${env_base} --display-name plant -o ~/.local/share/jupyter/kernels/plant/kernel.json
