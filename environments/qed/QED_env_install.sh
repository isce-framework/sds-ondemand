###########################################################################################
# "Copyright 2024, by the California Institute of Technology. ALL RIGHTS RESERVED. United States Government sponsorship acknowledged. Any commercial use must be negotiated 
# with the Office of Technology Transfer at the California Institute of Technology.",
#
# "This software may be subject to U.S. export control laws and regulations. By accepting this document, the user agrees to comply with all applicable U.S. export laws and 
# regulations. User has the responsibility to obtain export licenses, or other export authority as may be required, before exporting such information to foreign countries # 
# or providing access to foreign persons.\n",
###########################################################################################

############################################################# 
# Create QED env install script.
# Run script by typing in terminal: source QED_env_install.sh
#############################################################

# setup env path variables
user_home="/home/jovyan"
local_base="/home/jovyan/.local/envs"
env_base=${local_base}/qed

echo "******************"
echo "QED INSTALL SCRIPT"
echo "******************"

# Remove existing QED conda env if installed before installing the latest QEDversion
echo "***Checking if qed conda env already exists. Remove old version if it exists."
if conda info --envs | grep -q qed; then echo "***qed exists so attempting to remove old version. Please accept removal if prompted"; conda remove --name qed --all; else echo "qed env does not exist. No need to remove first. Proceeding with qed install"; fi

# Download qed.zip from S3 bucket, unzip and clean-up
# List available envs at S3 bucket location
echo "***Listing S3 bucket env available-> s3://nisar-st-data-ondemand/env/"
aws s3 ls s3://nisar-st-data-ondemand/env/

echo "***Download s3://nisar-st-data-ondemand/env/qed.zip from S3 bucket to $local_base"
# Copy qed.zip to your account
aws s3 cp s3://nisar-st-data-ondemand/env/qed.zip ${local_base}

# Unzip qed.zip to your .local/env/qed area. This step takes a long time (~20 mins) to unzip. Do not proceed forward until this step is done. [*] in the jupyternook cell will be replaced with a number when this cell is done
echo "***Unzipping qed.zip"
unzip ${local_base}/qed.zip -d ${user_home}

# Cleaning up qed.zip
echo "***Cleaning up and removing qed.zip"
rm ${local_base}/qed.zip


echo "***Finding python version for .pyre setup"
python_version=$(conda run -p ${env_base} python --version | awk '/Python/ {print $2}' | awk 'BEGIN { FS="." } { print $1"."$2 }')
echo "python_version="$python_version

echo "***Setup .pyre mm.pfg, config.mm, and qed.yaml"
mkdir -p /home/jovyan/.pyre
if [ -f /home/jovyan/.pyre/mm.pfg ]
then
     mv /home/jovyan/.pyre/mm.pfg /home/jovyan/.pyre/mm.pfg.${date_str}
fi
sed -e "s:@PREFIX@:${env_base}:g" qed_support_files/mm.pfg > /home/jovyan/.pyre/mm.pfg

mkdir -p /home/jovyan/.mm
if [ -f /home/jovyan/.mm/config.mm ]
then
     mv /home/jovyan/.mm/config.mm /home/jovyan/.mm/config.mm.${date_str}
fi
sed -e "s:@PYTHON_VERSION@:${python_version}:g" qed_support_files/config.mm > /home/jovyan/.mm/config.mm
if [ ! -f /home/jovyan/.pyre/qed.yaml ]
then
    cp qed_support_files/qed.yaml /home/jovyan/.pyre/qed.yaml
fi

echo "***If you see mm.pfg, config.mm, and qed.yaml, then setup .pyre was successful"
ls /home/jovyan/.pyre/

echo "***Setting up QED button"

# Setup config files
if [ ! -f ${user_home}/.pyre/qed.yaml ]
then
    curl https://raw.githubusercontent.com/isce-framework/sds-ondemand/main/environments/qed/qed_support_files/qed.yaml ${user_home}/.pyre/qed.yaml
fi

# Add QED button to jupyter env
mkdir -p ${user_home}/.jupyter
if [ -f ${user_home}/.jupyter/jupyter_notebook_config.py ]
then
    mv ${user_home}/.jupyter/jupyter_notebook_config.py ${user_home}/.jupyter/jupyter_notebook_config.py.${date_str}
fi
curl https://raw.githubusercontent.com/isce-framework/sds-ondemand/main/environments/qed/qed_support_files/jupyter_notebook_config.py.ops --output ${user_home}/.jupyter/jupyter_notebook_config.py


# update the ipykernel to recognize the new kernel
conda run -n qed python -m ipykernel install --user --name qed --display-name "qed"
# now invoke kernda to modify the kernel file to ensure the kernel is invoked from within the conda environment
pip install kernda
kernda --env-dir ${env_base} --display-name qed -o ~/.local/share/jupyter/kernels/qed/kernel.json