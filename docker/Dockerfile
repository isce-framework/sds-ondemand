FROM cae-artifactory.jpl.nasa.gov:16001/gov/nasa/jpl/nisar/sds/pcm/nisar_ade:r1.4a

ENV HOME=/home/jovyan \
    CONDA_DIR=/opt/conda

USER root
RUN $CONDA_DIR/bin/pip install 'ipykernel<5.0.0'
RUN $CONDA_DIR/bin/pip install rasterio
RUN $CONDA_DIR/bin/pip install folio

RUN cd $HOME \
    && git clone https://github.com/hysds/notebook_pge_wrapper.git \
    && cd notebook_pge_wrapper \
    && $CONDA_DIR/bin/pip install -e .
    

USER jovyan
COPY . /home/jovyan/nisar-on-demand-use-cases 

WORKDIR $HOME

CMD ["/bin/bash", "--login"]
