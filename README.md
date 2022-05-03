# sds-ondemand
#### NISAR's SDS ondemand tutorials

Created by: Jimmie D. Young (Jet Propulsion Laboratory, California Institute of Technology), Ekaterina Tymofyeyeva (Jet Propulsion Laboratory, California Institute of Technology)

This research was carried out at the Jet Propulsion Laboratory, California Institute of Technology, and was sponsored by the National Aeronautics and Space Administration (80NM0018D0004).

Copyright 2022 California Institute of Technology. Government sponsorship acknowledged.

#### Note for Science Team Meeting - 2022-05-03

Some of the notebooks contained in this repository cannot currently be executed, awaiting public release of NISAR DEMs. As soon as those become available, we will verify the remaining notebooks and inform the user community.

The following notebooks have been vetted and verified to run in the current environment: 
* environments/Create_Environments
* 01-Introduction
* 02.1-Datasets.geospatial
* 03-ISCE3-L1-L-RSLC
* L1_L_RSLC-Analysis
* smallbaselineapp

Those dependent on NISAR DEMs are:
* 04-NISAR_DEM_notebook
* 05-Tunable_Parameters
* ARIAtools
* Data-Access
* L1_RSLC_to_L2_GSLC
* LostHills_time_series
* maap-plant-demo_20191206
* plotting-examples
* topsStack_parallel
* topsStack
* topsStackIfgExample

#### NISAR on-demand use cases assume the following:

- end users (ADT, Cal/Val, project science users) will perform algorithm development and/or analysis using jupyter notebooks
- jupyter notebooks will have access to the ISCE3 SAS and a yet to be determined set of software
- jupyter notebooks will run on infrastructure that is collocated with SDS and SDS resources (S3 buckets) to take advantage of the NISAR SDS data lake

That being said, the set of jupyter notebooks in this repo can be run on any instance (cloud or on-premise including your laptop as long as access to necessary resources is available).

## Repository structure

This repository is laid out in the following manner:

```
sds-ondemand
├── *.ipynb                   The primary use case notebooks
├── environments              Directory containing notebook(s) to create science data processing conda environments and jupyter kernels
├── support_docs
   ├── smallbaselineApp       Supporting image files for the smallbaselineApp notebook.
   ├── topsApp                Supporting image and document files for the topsApp notebook.
   └── other_notebooks        Other notebooks of potential interest, not covered in the user's guide.
├── python                    Supporting python scripts referenced in the notebooks.
├── notebook_output           Location of notebook downloads and generated data files, each notebook creates its own subdirectory.
├── docker                    Directory containing dockerfile and support files for notebook(s) to be processed at scale
└── notebook_pges             Directory containing notebooks to be processed at scale
```

