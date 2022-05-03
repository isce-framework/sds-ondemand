#Copyright 2021, by the California Institute of Technology. ALL RIGHTS RESERVED. United States Government sponsorship acknowledged. Any commercial use must be negotiated with the Office of Technology Transfer at the California Institute of Technology.</font>
#This software may be subject to U.S. export control laws and regulations. By accepting this document, the user agrees to comply with all applicable U.S. export laws and regulations. User has the responsibility to obtain export licenses, or other export authority as may be required, before exporting such information to foreign countries or providing access to foreign persons.<font>

from shutil import copyfile, move # Utilities for copying and moving files
from osgeo import gdal            # GDAL support for reading virtual files
import os                         # To create and remove directories
import matplotlib.pyplot as plt   # For plotting
import numpy as np                # Matrix calculations
import glob                       # Retrieving list of files
import boto3                      # For talking to s3 bucket
import rasterio as rio
from rasterio.plot import show, plotting_extent
from rasterio.merge import merge

def plot_wrapped_data_multiframe(frame_list):
    import os
    import folium
    from glob import glob
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio as rio
    from rasterio.plot import show, plotting_extent
    from rasterio.merge import merge
    from PIL import Image, ImageChops


    # plot wrapped IFGs individually
    flat_plots = []
    flat_bboxes = []
    for i, file in enumerate(frame_list):
        src = rio.open(file)
        fig, ax = plt.subplots(1, figsize=(18, 16))
        data = src.read(1)
        data[data==0] = np.nan
        show(np.angle(data), cmap='rainbow', vmin=-np.pi, vmax=np.pi, transform=src.transform, ax=ax)
        png_file = f'flat_{i}.png'
        fig.savefig(png_file, transparent=True)
        flat_plots.append(png_file)
        flat_bboxes.append(src.bounds)

def plot_wrapped_data_singleframe(filename='merged/filt_topophase.flat.geo'):
    import os
    import folium
    from glob import glob
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio as rio
    from rasterio.plot import show, plotting_extent
    from rasterio.merge import merge
    from PIL import Image, ImageChops


    src = rio.open(filename)

    fig, ax = plt.subplots(1, figsize=(18, 16))
    data = src.read(1)
    data[data==0] = np.nan
    show(np.angle(data), cmap='rainbow', vmin=-np.pi, vmax=np.pi, transform=src.transform, ax=ax)
    png_file = f'flat.png'
    fig.savefig(png_file, transparent=True)

def plotdata(GDALfilename, band=1,
             title=None,colormap='gray',
             aspect=1, background=None,
             datamin=None, datamax=None,
             interpolation='nearest',
             nodata = None,
             draw_colorbar=True, colorbar_orientation="horizontal"):
    
    # Read the data into an array
    ds = gdal.Open(GDALfilename, gdal.GA_ReadOnly)
    data = ds.GetRasterBand(band).ReadAsArray()
    transform = ds.GetGeoTransform()
    ds = None
    
    try:
        if nodata is not None:
            data[data == nodata] = np.nan
    except:
        pass
        
    # getting the min max of the axes
    firstx = transform[0]
    firsty = transform[3]
    deltay = transform[5]
    deltax = transform[1]
    lastx = firstx+data.shape[1]*deltax
    lasty = firsty+data.shape[0]*deltay
    ymin = np.min([lasty,firsty])
    ymax = np.max([lasty,firsty])
    xmin = np.min([lastx,firstx])
    xmax = np.max([lastx,firstx])

    # put all zero values to nan and do not plot nan
    if background is None:
        try:
            data[data==0]=np.nan
        except:
            pass
    
    fig = plt.figure(figsize=(18, 16))
    ax = fig.add_subplot(111)
    cax = ax.imshow(data, vmin = datamin, vmax=datamax,
                    cmap=colormap, extent=[xmin,xmax,ymin,ymax],
                    interpolation=interpolation)
    ax.set_title(title)
    if draw_colorbar is not None:
        cbar = fig.colorbar(cax,orientation=colorbar_orientation)
    ax.set_aspect(aspect)    
    plt.show()
    
    # clearing the data
    data = None


def plot_wrapped_multifiles(files, figsize=(20, 30)):
    files_to_mosaic = []
    for file in files: #glob("hello_world*/filt_topophase.flat.geo"):
        src = rio.open(file)
        files_to_mosaic.append(src)
    
    mosaic, out_trans = merge(files_to_mosaic, nodata=0)

    mosaic[mosaic==0] = np.nan
    fig, ax = plt.subplots(1, figsize=figsize)
    show(np.angle(mosaic[0]), cmap='rainbow', vmin=-np.pi, vmax=np.pi, ax=ax)

def plot_unwrapped_multifiles(files, figsize=(20, 30)):
    files_to_mosaic = []
    for file in files:
        src = rio.open(file)
        files_to_mosaic.append(src)
    
    mosaic, out_trans = merge(files_to_mosaic, nodata=0)

    mosaic[mosaic==0] = np.nan
    fig, ax = plt.subplots(1, figsize=figsize)
    show(mosaic[1], cmap='jet', vmin=-20, vmax=50, ax=ax)



# Utility to plot interferograms
def plotcomplexdata(GDALfilename,
                    title=None, aspect=1,
                    datamin=None, datamax=None,
                    interpolation='nearest',
                    draw_colorbar=None, colorbar_orientation="horizontal"):
    # Load the data into numpy array
    ds = gdal.Open(GDALfilename, gdal.GA_ReadOnly)
    slc = ds.GetRasterBand(1).ReadAsArray()
    transform = ds.GetGeoTransform()
    ds = None
    
    # getting the min max of the axes
    firstx = transform[0]
    firsty = transform[3]
    deltay = transform[5]
    deltax = transform[1]
    lastx = firstx+slc.shape[1]*deltax
    lasty = firsty+slc.shape[0]*deltay
    ymin = np.min([lasty,firsty])
    ymax = np.max([lasty,firsty])
    xmin = np.min([lastx,firstx])
    xmax = np.max([lastx,firstx])

    # put all zero values to nan and do not plot nan
    try:
        slc[slc==0]=np.nan
    except:
        pass

    
    fig = plt.figure(figsize=(18, 16))
    ax = fig.add_subplot(1,2,1)
    cax1=ax.imshow(np.abs(slc), vmin = datamin, vmax=datamax,
                   cmap='gray', extent=[xmin,xmax,ymin,ymax],
                   interpolation=interpolation)
    ax.set_title(title + " (amplitude)")
    if draw_colorbar is not None:
        cbar1 = fig.colorbar(cax1,orientation=colorbar_orientation)
    ax.set_aspect(aspect)

    ax = fig.add_subplot(1,2,2)
    cax2 =ax.imshow(np.angle(slc), cmap='rainbow',
                    vmin=-np.pi, vmax=np.pi,
                    extent=[xmin,xmax,ymin,ymax],
                    interpolation=interpolation)
    ax.set_title(title + " (phase [rad])")
    if draw_colorbar is not None:
        cbar2 = fig.colorbar(cax2, orientation=colorbar_orientation)
    ax.set_aspect(aspect)
    plt.show()
    
    # clearing the data
    slc = None

# Utility to plot multiple similar arrays
def plotstackdata(GDALfilename_wildcard, band=1,
                  title=None, colormap='gray',
                  aspect=1, datamin=None, datamax=None,
                  interpolation='nearest',
                  draw_colorbar=True, colorbar_orientation="horizontal"):
    # get a list of all files matching the filename wildcard criteria
    GDALfilenames = glob.glob(GDALfilename_wildcard)
    
    # initialize empty numpy array
    data = None
    for GDALfilename in GDALfilenames:
        ds = gdal.Open(GDALfilename, gdal.GA_ReadOnly)
        data_temp = ds.GetRasterBand(band).ReadAsArray()   
        ds = None
        
        if data is None:
            data = data_temp
        else:
            data = np.vstack((data,data_temp))

    # put all zero values to nan and do not plot nan
    try:
        data[data==0]=np.nan
    except:
        pass            
            
    fig = plt.figure(figsize=(18, 16))
    ax = fig.add_subplot(111)
    cax = ax.imshow(data, vmin = datamin, vmax=datamax,
                    cmap=colormap, interpolation=interpolation)
    ax.set_title(title)
    if draw_colorbar is not None:
        cbar = fig.colorbar(cax,orientation=colorbar_orientation)
    ax.set_aspect(aspect)    
    plt.show() 

    # clearing the data
    data = None

# Utility to plot multiple simple complex arrays
def plotstackcomplexdata(GDALfilename_wildcard,
                         title=None, aspect=1,
                         datamin=None, datamax=None,
                         interpolation='nearest',
                         draw_colorbar=True, colorbar_orientation="horizontal"):
    # get a list of all files matching the filename wildcard criteria
    GDALfilenames = glob.glob(GDALfilename_wildcard)
    print(GDALfilenames)
    # initialize empty numpy array
    data = None
    for GDALfilename in GDALfilenames:
        ds = gdal.Open(GDALfilename, gdal.GA_ReadOnly)
        data_temp = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        
        if data is None:
            data = data_temp
        else:
            data = np.vstack((data,data_temp))

    # put all zero values to nan and do not plot nan
    try:
        data[data==0]=np.nan
    except:
        pass              
            
    fig = plt.figure(figsize=(18, 16))
    ax = fig.add_subplot(1,2,1)
    cax1=ax.imshow(np.abs(data), vmin=datamin, vmax=datamax,
                   cmap='gray', interpolation='nearest')
    ax.set_title(title + " (amplitude)")
    if draw_colorbar is not None:
        cbar1 = fig.colorbar(cax1,orientation=colorbar_orientation)
    ax.set_aspect(aspect)

    ax = fig.add_subplot(1,2,2)
    cax2 =ax.imshow(np.angle(data), cmap='rainbow',
                            interpolation='nearest')
    ax.set_title(title + " (phase [rad])")
    if draw_colorbar is not None:
        cbar2 = fig.colorbar(cax2,orientation=colorbar_orientation)
    ax.set_aspect(aspect)
    plt.show() 
    
    # clearing the data
    data = None


def plot_multidata(GDALfilename_dict, band=1,
             title=None,colormap='gray',
             aspect=1, background=None,
             datamin=None, datamax=None,
             interpolation='nearest',
             nodata = None,
             draw_colorbar=True, colorbar_orientation="horizontal"):
    
    import math

    n = len(GDALfilename_dict.keys())
    row = math.ceil(n/2)
    fig = plt.figure(figsize=(18, 16))
    
    for i, key in enumerate(GDALfilename_dict):
        title = key
        GDALfilename = GDALfilename_dict[key]
        
        # Read the data into an array
        ds = gdal.Open(GDALfilename, gdal.GA_ReadOnly)
        data = ds.GetRasterBand(band).ReadAsArray()
        transform = ds.GetGeoTransform()
        ds = None
    
        try:
            if nodata is not None:
                data[data == nodata] = np.nan
        except:
            pass
        
        # getting the min max of the axes
    
        firstx = transform[0]
        firsty = transform[3]
        deltay = transform[5]
        deltax = transform[1]
        lastx = firstx+data.shape[1]*deltax
        lasty = firsty+data.shape[0]*deltay
        ymin = np.min([lasty,firsty])
        ymax = np.max([lasty,firsty])
        xmin = np.min([lastx,firstx])
        xmax = np.max([lastx,firstx])
    
        # put all zero values to nan and do not plot nan
        if background is None:
            try:
                data[data==0]=np.nan
            except:
                pass
        ax = fig.add_subplot(row, 2, i+1)
        cax=ax.imshow(data, vmin = datamin, vmax=datamax,
                    cmap=colormap, extent=[xmin,xmax,ymin,ymax],
                    interpolation=interpolation)
        ax.set_title(title)
        if draw_colorbar is not None:
            cbar = fig.colorbar(cax,orientation=colorbar_orientation)
           
    plt.show()
    
    # clearing the data
    data = None
