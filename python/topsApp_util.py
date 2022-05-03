#Copyright 2021, by the California Institute of Technology. ALL RIGHTS RESERVED. United States Government sponsorship acknowledged. Any commercial use must be negotiated with the Office of Technology Transfer at the California Institute of Technology.</font>
#This software may be subject to U.S. export control laws and regulations. By accepting this document, the user agrees to comply with all applicable U.S. export laws and regulations. User has the responsibility to obtain export licenses, or other export authority as may be required, before exporting such information to foreign countries or providing access to foreign persons.<font>

from shutil import copyfile, move # Utilities for copying and moving files
from osgeo import gdal            # GDAL support for reading virtual files
import os                         # To create and remove directories
import matplotlib.pyplot as plt   # For plotting
import numpy as np                # Matrix calculations
import glob                       # Retrieving list of files
import boto3                      # For talking to s3 bucket
import os
import json
from math import floor, ceil
import json
import re
import osaka
import osaka.main
from builtins import str
import os, sys, re, json, logging, traceback, requests, argparse
from datetime import datetime
from pprint import pformat
from requests.packages.urllib3.exceptions import (InsecureRequestWarning,
                                                  InsecurePlatformWarning)
import isce
from iscesys.Component.ProductManager import ProductManager as PM
import rasterio as rio
from rasterio.plot import show, plotting_extent
from rasterio.merge import merge

try: from html.parser import HTMLParser
except: from html.parser import HTMLParser
    
log_format = "[%(asctime)s: %(levelname)s/%(funcName)s] %(message)s"
logging.basicConfig(format=log_format, level=logging.INFO)
logger = logging.getLogger('create_ifg')

        
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)
PROCESSING_START=datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

PGE_BASE=os.getcwd()
ISCE_HOME="/opt/isce2/isce"

SLC_RE = re.compile(r'(?P<mission>S1\w)_IW_SLC__.*?' +
                    r'_(?P<start_year>\d{4})(?P<start_month>\d{2})(?P<start_day>\d{2})' +
                    r'T(?P<start_hour>\d{2})(?P<start_min>\d{2})(?P<start_sec>\d{2})' +
                    r'_(?P<end_year>\d{4})(?P<end_month>\d{2})(?P<end_day>\d{2})' +
                    r'T(?P<end_hour>\d{2})(?P<end_min>\d{2})(?P<end_sec>\d{2})_.*$')


QC_SERVER = 'https://qc.sentinel1.eo.esa.int/'
DATA_SERVER = 'http://aux.sentinel1.eo.esa.int/'

ORBITMAP = [('precise','aux_poeorb', 100),
            ('restituted','aux_resorb', 100)]

OPER_RE = re.compile(r'S1\w_OPER_AUX_(?P<type>\w+)_OPOD_(?P<yr>\d{4})(?P<mo>\d{2})(?P<dy>\d{2})')
sensor_name = "SENTINEL1"
swaths = [3]
range_looks = 7
azimuth_looks = 3
do_unwrap = "True"
unwrapper_name = "snaphu_mcf"
do_denseoffsets = "False"

# defining backup dirs in case of download issues on the local server
s3 = boto3.resource("s3")
data_backup_bucket = s3.Bucket("asf-jupyter-data")
data_backup_dir = "TOPS"

# Utility to plot a 2D array
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
    
class MyHTMLParser(HTMLParser):

    def __init__(self):
        HTMLParser.__init__(self)
        self.fileList = []
        self.pages = 0
        self.in_td = False
        self.in_a = False
        self.in_ul = False

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.in_td = True
        elif tag == 'a' and self.in_td:
            self.in_a = True
        elif tag == 'ul':
            for k,v in attrs:
                if k == 'class' and v.startswith('pagination'):
                    self.in_ul = True
        elif tag == 'li' and self.in_ul:
            self.pages += 1

    def handle_data(self,data):
        if self.in_td and self.in_a:
            if OPER_RE.search(data):
                self.fileList.append(data.strip())

    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_td = False
            self.in_a = False
        elif tag == 'a' and self.in_td:
            self.in_a = False
        elif tag == 'ul' and self.in_ul:
            self.in_ul = False
        elif tag == 'html':
            if self.pages == 0:
                self.pages = 1
            else:
                # decrement page back and page forward list items
                self.pages -= 2

def session_get(session, url):
    return session.get(url, verify=False)

def get_download_orbit_dict(download_orbit_dict, slc_date, mission_type):
    

    logger.info("slc_date : {}".format(slc_date))
    url = "https://qc.sentinel1.eo.esa.int/aux_poeorb/?validity_start={}&sentinel1__mission={}".format(slc_date, mission_type)
    session = requests.Session()
    r = session_get(session, url)
    r.raise_for_status()
    parser = MyHTMLParser()
    parser.feed(r.text)

    for res in parser.fileList:
        #id = "%s-%s" % (os.path.splitext(res)[0], dataset_version)
        match = OPER_RE.search(res)
        if not match:
            raise RuntimeError("Failed to parse orbit: {}".format(res))
        download_orbit_dict[res] = os.path.join(DATA_SERVER, "/".join(match.groups()), "{}.EOF".format(res))
        #yield id, results[id]
        
    #logger.info(results)
    
    return download_orbit_dict

def get_orbit_files(localize_slcs):
    from datetime import datetime, timedelta
    import json
    import os
    import osaka
    import osaka.main
    
    orbit_dict = {}

    orbit_dates = []
    
    for slc in localize_slcs:
        match = SLC_RE.search(slc)
        if not match:
            raise RuntimeError("Failed to recognize SLC ID %s." %slc)
        mission = match.group('mission')
        day_dt_str = "{}-{}-{}".format(match.group('start_year'), 
                                       match.group('start_month'), match.group('start_day'))
        
        day_dt = datetime.strptime(day_dt_str, '%Y-%m-%d') - timedelta(days=1)
        
        day_dt_str = day_dt.strftime('%Y-%m-%d')
        
        logger.info("day_dt_str : {}".format(day_dt_str))
        if day_dt_str not in orbit_dates:
            orbit_dates.append(day_dt_str)
            orbit_dict = get_download_orbit_dict(orbit_dict, day_dt_str, mission)
            directory = orbit_dir
            if not os.path.exists(directory):
                os.makedirs(directory)
            #directory = os.path.join(wd, "orbits")
            for k, v in orbit_dict.items():
                osaka.main.get(v, directory)
         
    logger.info("orbit_dict : %s " %json.dumps(orbit_dict, indent=4))

def get_area(coords):
    '''get area of enclosed coordinates- determines clockwise or counterclockwise order'''
    from past.utils import old_div
    
    n = len(coords) # of corners
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i][1] * coords[j][0]
        area -= coords[j][1] * coords[i][0]
    #area = abs(area) / 2.0
    return old_div(area, 2)

def download_slc(slc_id, path):
    url = "https://datapool.asf.alaska.edu/SLC/SA/{}.zip".format(slc_id)
    logger.info("Downloading {} : {}".format(slc_id, url))
    
    if not os.path.exists(path):
        os.makedirs(path)
    osaka.main.get(url, path)

def run_cmd_output(cmd):
    from subprocess import check_output, CalledProcessError
    cmd_line = " ".join(cmd)
    logger.info("Calling: {}".format(cmd_line))
    output = check_output(cmd_line, shell=True)
    return output

def run_cmd(cmd):
    import subprocess
    from subprocess import check_call, CalledProcessError
    import sys
    cmd_line = " ".join(cmd)
    logger.info("Calling : {}".format(cmd_line))
    p = subprocess.Popen(cmd_line, shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    while True: 
        line = p.stdout.readline()
        if not line:
            break
        logger.info(line.strip())
        sys.stdout.flush()
        
def download_dem(min_lat, max_lat, min_lon, max_lon):
    from math import floor, ceil
    min_lat_lo = floor(min_lat)
    max_lat_hi = ceil(max_lat)
    min_lon_lo = floor(min_lon)
    max_lon_hi = ceil(max_lon)
    ISCE_HOME="/opt/isce2/isce"
    
    dem_cmd = [
        "{}/applications/dem.py".format(ISCE_HOME), "-a",
        "stitch", "-b", "{} {} {} {}".format(min_lat_lo, max_lat_hi, min_lon_lo, max_lon_hi),
        "-r", "-s", "1", "-f", "-c", "|", "tee", "dem.txt"
        #"-n", dem_user, "-w", dem_pass,"-u", dem_url
    ]
    run_cmd(dem_cmd)
        
def download_slcs(localize_slcs, path):
    for slc in localize_slcs:
        download_slc(slc, path) 
        
def get_start_end_times(localize_slcs):
    #"S1A_IW_SLC__1SDV_20200511T135117_20200511T135144_032518_03C421_7768"
    import re
    import datetime
    
    start_times = []
    end_times = []
    SLC_RE1 = re.compile(r'(?P<mission>S1\w)_IW_SLC__.*?_(?P<start_time>\d{8}T\d{6})_(?P<end_time>\d{8}T\d{6})_.*$')
    for slc in localize_slcs:
        match = SLC_RE1.search(slc)
        if not match:
            raise RuntimeError("Failed to recognize SLC ID %s." %slc)
        start_time_str = "{}".format(match.group('start_time'))
        start_times.append(datetime.datetime.strptime(start_time_str, '%Y%m%dT%H%M%S'))
        end_time_str = "{}".format(match.group('end_time'))
        end_times.append(datetime.datetime.strptime(end_time_str, '%Y%m%dT%H%M%S'))
    return sorted(start_times)[0], sorted(end_times)[-1]
                                     
        
def xml2string(xmlroot, encoding="UTF-8", method="xml", indent="\t", newl="\n"):
    from xml.dom import minidom
    import xml.etree.cElementTree as ET
    
    xmlstring = minidom.parseString(ET.tostring(xmlroot, encoding=encoding, method=method))\
        .toprettyxml(newl=newl, indent=indent)
    return xmlstring

def create_xml(xml_file, doc_type, slcs):
    from xml.dom import minidom 
    import xml.etree.cElementTree as ET
    import os 
   
    slc_list = []
    for slc in slcs:
        slc_list.append(os.path.join('../data/slcs/', "{}.zip".format(slc)))

    

    comp_elem = ET.Element('component')
    comp_elem.set("name", doc_type)

    prop_elem = ET.SubElement(comp_elem, 'property') 
    prop_elem.set('name', 'orbit directory')
    prop_elem.text='../data/orbits'

    prop_elem = ET.SubElement(comp_elem, 'property') 
    prop_elem.set('name', 'output directory')
    prop_elem.text=doc_type
    
    prop_elem = ET.SubElement(comp_elem, 'property') 
    prop_elem.set('name', 'safe')
    prop_elem.text=str(slc_list)


    xml_str = xml2string(comp_elem) 

    with open(xml_file, 'w') as fw:
        fw.write(xml_str)
        
def create_dataset_json(id, version, met_file, ds_file):
    """Write dataset json."""


    # get metadata
    with open(met_file) as f:
        md = json.load(f)

    # build dataset
    ds = {
        'creation_timestamp': "%sZ" % datetime.utcnow().isoformat(),
        'version': version,
        'label': id
    }

    try:
        
        
        
        logger.info("create_dataset_json : met['bbox']: %s" %md['bbox'])
        
        coordinates = [
                    [
                      [ md['bbox'][0][1], md['bbox'][0][0] ],
                      [ md['bbox'][3][1], md['bbox'][3][0] ],
                      [ md['bbox'][2][1], md['bbox'][2][0] ],
                      [ md['bbox'][1][1], md['bbox'][1][0] ],
                      [ md['bbox'][0][1], md['bbox'][0][0] ]
                    ] 
                  ]
        
     
        #coordinates = md['union_geojson']['coordinates']
    
        cord_area = get_area(coordinates[0])
        if not cord_area>0:
            logger.info("creating dataset json. coordinates are not clockwise, reversing it")
            coordinates = [coordinates[0][::-1]]
            logger.info(coordinates)
            cord_area = get_area(coordinates[0])
            if not cord_area>0:
                logger.info("creating dataset json. coordinates are STILL NOT  clockwise")
        else:
            logger.info("creating dataset json. coordinates are already clockwise")

        ds['location'] =  {'type': 'Polygon', 'coordinates': coordinates}
        logger.info("create_dataset_json location : %s" %ds['location'])

    except Exception as err:
        logger.info("create_dataset_json: Exception : ")
        logger.info(str(err))
        logger.info("Traceback: {}".format(traceback.format_exc()))


    # set earliest sensing start to starttime and latest sensing stop to endtime
    if isinstance(md['sensing_start'], str):
        ds['starttime'] = md['sensing_start']
    else:
        md['sensing_start'].sort()
        ds['starttime'] = md['sensing_start'][0]

    if isinstance(md['sensing_stop'], str):
        ds['endtime'] = md['sensing_stop']
    else:
        md['sensing_stop'].sort()
        ds['endtime'] = md['sensing_stop'][-1]

    # write out dataset json
    with open(ds_file, 'w') as f:
        json.dump(ds, f, indent=2)
        

def get_tops_subswath_xml(masterdir):
    ''' 
        Find all available IW[1-3].xml files
    '''

    logger.info("get_tops_subswath_xml from : %s" %masterdir)

    masterdir = os.path.abspath(masterdir)
    IWs = glob(os.path.join(masterdir,'IW*.xml'))
    if len(IWs)<1:
        raise Exception("Could not find a IW*.xml file in " + masterdir)

    return IWs

def read_isce_product(xmlfile):
    logger.info("read_isce_product: %s" %xmlfile)

    # check if the file does exist
    check_file_exist(xmlfile)

    # loading the xml file with isce
    pm = PM()
    pm.configure()
    obj = pm.loadProduct(xmlfile)
    return obj

def check_file_exist(infile):
    logger.info("check_file_exist : %s" %infile)
    if not os.path.isfile(infile):
        raise Exception(infile + " does not exist")
    else:
        logger.info("%s Exists" %infile)


def get_tops_metadata(masterdir):

    logger.info("get_tops_metadata from : %s" %masterdir)
    # get a list of avialble xml files for IW*.xml
    IWs = get_tops_subswath_xml(masterdir)
    # append all swaths togheter
    frames=[]
    for IW  in IWs:
        logger.info("get_tops_metadata processing : %s" %IW)
        obj = read_isce_product(IW)
        frames.append(obj)

    output={}
    dt = min(frame.sensingStart for frame in frames)
    output['sensingStart'] =  dt.isoformat('T') + 'Z'
    logger.info(dt)
    dt = max(frame.sensingStop for frame in frames)
    output['sensingStop'] = dt.isoformat('T') + 'Z'
    logger.info(dt)
    return output
        
def extract_slc_data(slc_dir, slcs):
    from zipfile import ZipFile
    os.chdir(slc_dir)
    for slc in slcs:
        i = "{}.zip".format(slc)
        with ZipFile(i, 'r') as zf:
            zf.extractall()
            
def create_product(insar_dir, tops_properties, data_dict):
            
    from datetime import datetime
    from glob import glob
    import shutil

    os.chdir(insar_dir)
    print(insar_dir)

    #output = get_tops_metadata('fine_interferogram')
    #sensing_start= output['sensingStart']
    #sensing_stop = output['sensingStop']
    #logger.info("sensing_start : %s" %sensing_start)
    #logger.info("sensing_stop : %s" %sensing_stop)


    now=datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    dataset_name = "hello_world-product-{}-{}".format(now, "TopsApp")
    start_time, end_time = get_start_end_times(data_dict["localize_slcs"])
    print("{} : {}".format(start_time, end_time))
    #print(dataset_name)

    prod_dir = os.path.join(insar_dir, dataset_name)
    os.mkdir(prod_dir)

    met_file = os.path.join(dataset_name, "{}.met.json".format(dataset_name))
    dataset_file = os.path.join(dataset_name, "{}.dataset.json".format(dataset_name))

    met = tops_properties
    met["reference_slc"]= data_dict["reference_slcs"]
    met["secondary_slcs"] = data_dict["secondary_slcs"]
    met['sensing_start'] = start_time.isoformat('T') + 'Z'
    met['sensing_stop'] =  end_time.isoformat('T') + 'Z'
    met['start_time'] = start_time.isoformat('T') + 'Z'
    met['end_time'] = end_time.isoformat('T') + 'Z'

    min_lat = data_dict["min_lat"]
    max_lat = data_dict["max_lat"]
    min_lon = data_dict["min_lon"]
    max_lon = data_dict["max_lon"]

    bbox = [[min_lat, min_lon], [min_lat, max_lon], [max_lat, max_lon], [max_lat, min_lon]]
    met['bbox'] =  bbox 
    version = "v1.0"

    # generate dataset JSON
    with open(met_file, 'w') as f: json.dump(met, f, indent=2)
    
    # generate dataset JSON
    ds_file = os.path.join(prod_dir, "{}.dataset.json".format(dataset_name))
    create_dataset_json(dataset_name, version, met_file, ds_file)

    merged_dir = os.path.join(insar_dir, "merged")
    for name in glob("{}/*".format(merged_dir)):
    
        input_path = os.path.join(merged_dir, name)
        print(input_path)
        if os.path.isfile(input_path):
            #print("Copying {} to {}".format(input_path,  prod_dir ))
            shutil.copy(input_path,  prod_dir)
    return prod_dir
            
def create_topsApp_xml(tops_properties, input_dict):
    from xml.dom import minidom 
    import xml.etree.cElementTree as ET
    import os 

    supported_docs = os.path.join(tutorial_home_dir, 'support_docs', 'insar')
    os.makedirs(supported_docs, exist_ok=True)


    tops_xml_file = os.path.join(tutorial_home_dir, "support_docs/insar/topsApp.xml")

    root = ET.Element("topsApp")

    comp_elem = ET.SubElement(root, 'component')
    comp_elem.set("name", 'topsinsar')

    prop_elem = ET.SubElement(comp_elem, 'property') 
    prop_elem.set('name', 'Sensor name')
    prop_elem.text= input_dict['sensor_name']

    ref_elem = ET.SubElement(comp_elem, 'component')
    ref_elem.set("name", 'reference')

    ref_cat_elem = ET.SubElement(ref_elem, 'catalog')
    ref_cat_elem.text = "reference.xml"

    sec_elem = ET.SubElement(comp_elem, 'component')
    sec_elem.set("name", 'secondary')

    ref_cat_elem = ET.SubElement(sec_elem, 'catalog')
    ref_cat_elem.text = "secondary.xml"

    for k, v in tops_properties.items():
        prop_elem = ET.SubElement(comp_elem, 'property')
        prop_elem.set('name', k)
        prop_elem.text = str(v)

    prop_elem = ET.SubElement(comp_elem, 'property') 
    prop_elem.set('name', 'demfilename')
    prop_elem.text=input_dict['wgs84_file']
   
    xml_str = xml2string(root) 

    with open(tops_xml_file, 'w') as fw:
        #fw.write(r'<?xml version="1.0" encoding="UTF-8"?>\n')
        fw.write(xml_str)
