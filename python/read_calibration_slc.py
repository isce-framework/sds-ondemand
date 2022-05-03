#!/usr/bin/env python3

#Copyright 2021, by the California Institute of Technology. ALL RIGHTS RESERVED. United States Government sponsorship acknowledged. Any commercial use must be negotiated with the Office of Technology Transfer at the California Institute of Technology.</font>
#This software may be subject to U.S. export control laws and regulations. By accepting this document, the user agrees to comply with all applicable U.S. export laws and regulations. User has the responsibility to obtain export licenses, or other export authority as may be required, before exporting such information to foreign countries or providing access to foreign persons.<font>

import xml.etree.ElementTree as ET
import argparse
from argparse import RawTextHelpFormatter
import zipfile
import fnmatch
import re
import os
import sys        
import isce
import iscesys
import isceobj
import isceobj.Sensor.TOPS as TOPS
import isceobj.Sensor.TOPS.BurstSLC as BurstSLC
from isceobj.Image import createImage
import glob
from osgeo import gdal
import numpy as np
from scipy.interpolate import LinearNDInterpolator as interpnd
from iscesys.Parsers import XmlParser

def cmdLineParse():
    '''
    Command line parser.
    '''
    parser = argparse.ArgumentParser(
            description='Apply radiometric calibration to Sentinel SLC data',
            formatter_class=RawTextHelpFormatter,
            epilog='''
Example:

To run radiometric and thermal noise calibration on a zip file, using vh-pol data, within a given extent:

read_calibration_slc.py -zip S1A_IW_SLC__1SDV_20150315T231319_20150315T231349_005049_006569_0664.zip -od 20150315 -ext 34.6 34.65 -79.08 -78.97 -o -p vh -t noise

To run radiometric calibration only using the topsApp.xml and scene xml file (using default vv-pol):

read_calibration_slc.py -i topsApp.py -is s1_20150315.xml -o -t radio 

To output the radiometric calibration file only

read_calibration_slc.py -zip S1A_IW_SLC__1SDV_20150315T231319_20150315T231349_005049_006569_0664.zip -od 20150315 -oc

To output the radiometric and thermal noise calibration file (radio + noise) within a given extent

read_calibration_slc.py -zip S1A_IW_SLC__1SDV_20150315T231319_20150315T231349_005049_006569_0664.zip -od 20150315 -o -ext 34.6 34.65 -79.08 -78.97 -t noise

''')
    parser.add_argument('-i', type=str, required=False, dest='fxml',
            help = 'Input topsApp xml file. Ex: topsApp.xml')
    parser.add_argument('-is', type=str, required=False, dest='fxmlscene',
            help = 'Input scene xml file. Ex: s1a_master.xml')
    parser.add_argument('-zip', '--zipfile', nargs='+', required=False, dest='fin',
            help = 'Input filename of Sentinel SLC data; can be SAFE or .zip')
    parser.add_argument('-od', '--output_dir',  type=str, required=False, dest='odir',
            help = 'Output directory for calibration file and calibrated image.')
    parser.add_argument('-o', '--output', action='store_true', required=False, dest='output',
            help = 'Output calibrated image.')
    parser.add_argument('-ext', '--crop_extent', nargs='+', required=False, dest='ext',
            help = 'Provide lat lon extent (S N W E and no space in between). Ex: 10 20 110 120')
    parser.add_argument('-n', '--swath_num', dest='swath_num', type=str, default='1 2 3',
            help="A list of swaths to be processed. -- Default : '1 2 3'")
    parser.add_argument('-p', '--pol', type=str, required=False, default='vv', dest='pol',
            help = 'Polarization. Default is vv.  Can be vv or vh.')
    parser.add_argument('-t', '--type', type=str, required=False, default='radio', dest='type',
            help = 'Grab calibration type.  Can be radio (default), noise (radiometric calibration will also be done)')
    parser.add_argument('-oc', '--output_cali', action='store_true', required=False, dest='oc',
            help = 'Output the calibration files (under -od directory).')
    parser.add_argument('-ck', '--check_mode', action='store_true', required=False, dest='ck',
            help = 'Check mode. Unlink the SAVE file if the LUT contains zero. Not deleting actual SAFE files.')

    if len(sys.argv) < 2:
        print
        parser.print_help()
        print
        sys.exit(1)
    inps = parser.parse_args()

    # Sanity check
    if ( inps.fxml and inps.fin ) or ( inps.fxmlscene and inps.fin ):
        print('Can only provide xmls (-i, -is) OR the input zip file with ext (-zip, -ext)')
        sys.exit(1)
    if ( inps.fxml and not inps.fxmlscene ) or ( inps.fxmlscene and not inps.fxml ):
        print('Need to provide topsApp.xml and scene xml (-i and -is) at the same time')
        sys.exit(1)
    if ( inps.fin and not inps.ext  ) or ( inps.ext and not inps.fin ) or \
       ( inps.fin and not inps.odir ) or ( inps.odir  and not inps.fin ):
        print('Need to use zip file (-zip), ext (-ext) and output dir (-od) at the same time')
        sys.exit(1)


    return inps

def locateCaliFile(slc,type,polid='vv'):
    swathid = 's1?-iw%d'%(slc.swathNumber)
#    polid = slc.polarization  #default is already set to 'vv'
    print('Using data polarization ', polid)
    match = None
    for dirname in slc.safe:
        match = None
        
        if dirname.endswith('.zip'):
            zf = zipfile.ZipFile(dirname, 'r')
            if type == 'radio':
                pattern = os.path.join('*SAFE','annotation','calibration','calibration-') + swathid + '-slc-' + polid + '*.xml'
                match = fnmatch.filter(zf.namelist(), pattern)
                if (len(match) == 0):
                    raise Exception('No radiometric calibration file found in zip file: {0}'.format(dirname))
                slc.radioCali.append('/vsizip/'+os.path.join(dirname, match[0]) )
                print('Found radiometric calibration files: ', slc.radioCali)
            elif type == 'noise':
                pattern = os.path.join('*SAFE','annotation','calibration','noise-') + swathid + '-slc-' + polid + '*.xml'
                zf = zipfile.ZipFile(dirname, 'r')
                match = fnmatch.filter(zf.namelist(), pattern)
                if (len(match) == 0):
                    raise Exception('No noise calibration file found in zip file: {0}'.format(dirname))
                slc.noiseCali.append('/vsizip/'+os.path.join(dirname, match[0]) )
                print('Found noise calibration files: ', slc.noiseCali)
            zf.close()
        
        else:
            if type == 'radio':
                pattern = os.path.join('annotation','calibration','calibration-') + swathid + '-slc-' + polid + '*.xml'
                match = glob.glob( os.path.join(dirname, pattern))
                if (len(match) == 0):
                    raise Exception('No radiometric calibration file found in {0}'.format(dirname))
                slc.radioCali.append(match[0])
                print('Found radiometric calibration files: ', slc.radioCali)
            elif type == 'noise':
                pattern = os.path.join('annotation','calibration','noise-') + swathid + '-slc-' + polid + '*.xml'
                match = glob.glob( os.path.join(dirname, pattern))
                if (len(match) == 0):
                    raise Exception('No noise calibration file found in {0}'.format(dirname))
                slc.noiseCali.append(match[0])
                print('Found noise calibration files: ', slc.noiseCali)

def sort_caliFiles(slc):
    if len(slc._tiffSrc)>0:
        radioCaliList = []
        noiseCaliList = []
        s1_pat = re.compile(".*(S1[AB]_.+?_\d{4}\d{2}\d{2}T.*).zip.*")
        for swath in range(len(slc._tiffSrc)):
            match = s1_pat.search(slc._tiffSrc[swath])
            if match:
                id_prefix=match.groups(1)[0]
            else:
                raise Exception('Unable to extract date in multi-slice scene: %s' %  slc._tiffSrc[swath])
            for slc_ind in range(len(slc.radioCali)):
                if id_prefix in slc.radioCali[slc_ind]:
                    radioCaliList.append(slc.radioCali[slc_ind])
       	        if id_prefix in slc.noiseCali[slc_ind]:
                    noiseCaliList.append(slc.noiseCali[slc_ind])
        slc.radioCali=radioCaliList
        slc.noiseCali=noiseCaliList        
       
    
def write2flt( data, lat, lon, outName, nanvalue=-9999.90039062 ):
    width = data.shape[1]
    length = data.shape[0]
    data[ (data == nanvalue) ] = 0
    outm = np.matrix(data,float32)
    gpmFile = open(outName, "wb")
    outm.tofile(gpmFile)
    gpmFile.close();

def write2xml( data, xFirst, yFirst, dx, dy, outName, projection='lat/lon'):
    length  = data.shape[0] 
    width   = data.shape[1] 
    xStep   = dx 
    yStep   = dy 
    proj    = projection
    xmlName = outName + '.xml'
    xmldict  = {'METADATA_LOCATION':xmlName,
                'data_type':'Float',
                'image_type':'BIL',
                'Coordinate1':{'size':width,'startingValue':xFirst,'delta':xStep},
                'Coordinate2':{'size':length,'startingValue':yFirst,'delta':yStep},
                'FILE_NAME':outName,
                'number_bands':1    }

    demImage = createImage()
    demImage.init(xmldict)
    demImage.renderHdr()

def readXMLDict(FileName):
    xml = XmlParser
    xml = XmlParser.XmlParser()
    tmpdict  = xml.parse(FileName)[0]
    xmldict = dict((k.replace(" ", "").lower(), value) for (k, value) in tmpdict.items())
    if xmldict == "":
        print("No dictionay loaded from "+FileName+". \n");
    else:
        return(xmldict);    


if __name__ == '__main__':

    inps = cmdLineParse()
    type = inps.type
    pol  = inps.pol

    if inps.fxml:
        sceneDict = readXMLDict(inps.fxmlscene)
        jobDict   = readXMLDict(inps.fxml)
        fin  = [s.strip() for s in sceneDict['safe'].strip('[]').split(',')]
        odir = str(sceneDict['outputdirectory'])
    else:
        fin  = inps.fin 
        odir = inps.odir 

    if inps.fxml:
        try: 
            ext  = [float(x) for x in jobDict['topsinsar']['regionofinterest'].strip('[]').split()]
        except:
            ext = []
    else:
        ext = [float(inps.ext[x]) for x in range(len(inps.ext))]
        
    type = inps.type
    if type not in ('radio','noise'):
        error('ERROR: type (-t) needs to be either radio or noise')

    try:
        if inps.fxml:
            swathList = jobDict['topsinsar']['swaths']
        else:
            swathList = inps.swath_num.split()
    except:
        swathList = [1, 2, 3]


    for swath in swathList:
        slc = TOPS.createSentinel1()
        slc.polarization = pol
        slc.safe = fin
        slc.swathNumber = int(swath)
        #slc.product = TOPS.createTOPSSwathSLCProduct()
        slc.regionOfInterest = ext
        slc.product.bursts = iscesys.Component.createTraitSeq('bursts')
        slc.output = os.path.join(odir,'IW{0}'.format(swath))
        try:
            slc.parse()
        except Exception as err:
            print('Could not extract swath {0} from {1}'.format(swath, slc.safe))
            print('Generated: ', err)
            continue
        #slc.parse()
        if len(slc.product.bursts) == 0:
            continue
        slc.radioCali = []
        slc.noiseCali = []
        locateCaliFile(slc,'radio',pol) 
        locateCaliFile(slc,'noise',pol) 
        sort_caliFiles(slc)
        if slc._numSlices == 1:
            slc.radioCali = (slc.product.numberOfBursts) * [slc.radioCali[0]]
            slc.noiseCali = (slc.product.numberOfBursts) * [slc.noiseCali[0]]
    
        ################# Output calibrated SLC filesi (-o option)  ######################
        if inps.output:  # generate raw and calibrated slc

            width  = slc._burstWidth
            length = slc._burstLength
  
            ####Check if aux file corrections are needed
            useAuxCorrections = False
            if ('002.36' in slc.product.processingSoftwareVersion) and (slc.auxFile is not None):
                useAuxCorrections = True
  
            ###If not specified, for single slice, use width and length from first burst
            if width is None:
                width = slc.product.bursts[0].numberOfSamples
  
            if length is None:
                length = slc.product.bursts[0].numberOfLines

            if os.path.isdir(slc.output):
                print('Output directory exists. Overwriting ...')
            else:
                print('Creating directory {0} '.format(slc.output))
                os.makedirs(slc.output)

            prevTiff  = None
            prevRadio = None
            prevNoise = None
            for index, burst in enumerate(slc.product.bursts):

                print('############################################')
                print('#  burst {} of IW{} '.format(index+1,swath))
                print('############################################')
                ####tiff for single slice
                if (len(slc._tiffSrc) == 0) and (len(slc.tiff)==1):
                    tiffToRead  = slc.tiff[0]
                    radioToRead = slc.radioCali[0]
                    noiseToRead = slc.noiseCali[0] 
                else: ##tiffSrc for multi slice
                    tiffToRead  = slc._tiffSrc[index]
                    radioToRead = slc.radioCali[index]
                    noiseToRead = slc.noiseCali[index]
                ###To minimize reads and speed up 
                if tiffToRead != prevTiff:
                    src=None
                    band=None
                    src = gdal.Open(tiffToRead, gdal.GA_ReadOnly)
                    fullWidth = src.RasterXSize
                    fullLength = src.RasterYSize
                    band = src.GetRasterBand(1)
                    prevTiff  = tiffToRead
                    xlist  = list(range(fullWidth))
                    ylist  = list(range(fullLength))
                    fullX, fullY = np.meshgrid(xlist, ylist)

                #### Thermal Noise Calibration (Optional)
                if ( noiseToRead != prevNoise ) and ( type == 'noise' ):
                    if noiseToRead.startswith('/vsizip'): # read from zip file
                       parts = noiseToRead.split(os.path.sep)
                       if parts[2] == '':
                           parts[2] = os.path.sep
                       zipname = os.path.join(*(parts[2:-4]))
                       fname = os.path.join(*(parts[-4:]))
                       if not os.path.isfile(zipname):
                           print('File ',zipname,' does not exist.')
                           sys.exit(1)
                       zf = zipfile.ZipFile(zipname, 'r')
                       xmlstr = zf.read(fname)
                    else: # Read out calibration from xml file
                        fid = open(noiseToRead)
                        xmlstr = fid.read()
                    ### Extract the calibration LUT
                    root   = ET.fromstring(xmlstr)
                    try:
                        caliRoot = root.find('noiseVectorList')
                        nVectors  = int(caliRoot.items()[0][1])
                    except:
                        caliRoot = root.find('noiseRangeVectorList')
                        nVectors  = int(caliRoot.items()[0][1])
                    xxn = [];
                    yyn = [];
                    zzn = [];
                    for child in caliRoot:
                        line  = int(child.find('line').text)
                        pixel = list(map(int, child.find('pixel').text.split()))
                        nPixel = int(child.find('pixel').items()[0][1])
                        try:
                            noiseLut = list(map(float, child.find('noiseLut').text.split()))
                        except:
                            noiseLut = list(map(float, child.find('noiseRangeLut').text.split()))
                        xxn = xxn + pixel
                        yyn = yyn + [line]*nPixel
                        zzn = zzn + noiseLut
                    if inps.ck:
                        if not any(zzn):  # if all-zeros in zzn
                            zf.close()
                            for izip in range(len(fin)):
                                print("All-zero noise LUT in: {}".format(fin[izip]))
                                if(os.path.islink(fin[izip])):
                                    print("{} is a symlink, doing unlink fo SLC with bad LUT".format(fin[izip]))
                                    os.unlink(fin[izip])
                                else:
                                    print('{} is not a symlink. Not removing file. Please run this again with symlinked files'.format(fin[izip]))
                        else:
                            print('LUT is okay for :', fin, '. Doing nothing.')
                            sys.exit(1)
                    else:    
                        npt = len(zzn)
                        coordn = np.hstack((np.array(xxn).reshape(npt,1),np.array(yyn).reshape(npt,1)))
                        noise  = np.array(zzn).reshape(npt,1)
                        print('Start 2D interpolation on noiseLut. This may take a while....')
                        interpfn2 = interpnd(coordn,noise)
                        noiseIntrp = interpfn2(fullX, fullY)
                        prevNoise = noiseToRead
                        if inps.oc:
                            ocfile = os.path.join(odir,'IW{0}'.format(swath),'noise-iw'+str(swath)+'.cal')
                            write2flt( noiseIntrp, ylist, xlist, ocfile )
                            write2xml( noiseIntrp, ylist[0], xlist[0], 1, 1, ocfile ) 
                            print('Writing noise calibration file to ', ocfile)

                #### Radio Calibration
                if radioToRead != prevRadio:
                    ### Locate radiometric calibration xml file
                    if radioToRead.startswith('/vsizip'): # read from zip file
                        parts = radioToRead.split(os.path.sep)
                        if parts[2] == '':
                            parts[2] = os.path.sep
                        zipname = os.path.join(*(parts[2:-4]))
                        fname = os.path.join(*(parts[-4:]))
                        if not os.path.isfile(zipname):
                            print('File ',zipname,' does not exist.')
                            sys.exit(1)
                        zf = zipfile.ZipFile(zipname, 'r')
                        xmlstr = zf.read(fname)
                    else: # Read out calibration from xml file
                        fid = open(radioToRead)
                        xmlstr = fid.read()
                    ### Extract the calibration LUT
                    root   = ET.fromstring(xmlstr)
                    caliRoot = root.find('calibrationVectorList')
                    nVectors  = int(caliRoot.items()[0][1])
                    xx = [];
                    yy = [];
                    zz = [];
                    for child in caliRoot:
                        line  = int(child.find('line').text)
                        pixel = list(map(int, child.find('pixel').text.split()))
                        nPixel = int(child.find('pixel').items()[0][1])
                        sigmaNought = list(map(float, child.find('sigmaNought').text.split()))
                        xx = xx + pixel
                        yy = yy + [line]*nPixel
                        zz = zz + sigmaNought
                    if inps.ck:
                        if not any(zz):  # if all-zeros in zz
                            zf.close()
                            for izip in range(len(fin)):
                                os.unlink(fin[izip]) 
                            print('All-zero radiometric calibration LUT. Remove the symbolic link file ',fin )
                    else: 
                        npt = len(zz)
                        coord = np.hstack((np.array(xx).reshape(npt,1),np.array(yy).reshape(npt,1)))
                        sigma  = np.array(zz).reshape(npt,1)
                        print('Start 2D interpolation on sigmaNought. This may take a while....')
                        interpfn1  = interpnd(coord,sigma)
                        sigmaIntrp = interpfn1(fullX, fullY)
                        prevRadio  = radioToRead
                        if inps.oc:   # read in calibration file
                            ocfile = os.path.join(odir,'IW{0}'.format(swath),'radio-iw'+str(swath)+'.cal')
                            write2flt( sigmaIntrp, ylist, xlist, ocfile )
                            write2xml( sigmaIntrp, ylist[0], xlist[0], 1, 1, ocfile ) 
                            print('Writing radiometric calibration file to ', ocfile)

                if inps.ck:
                    sys.exit(0)

                #outfile1 = os.path.join(slc.output, 'burst_%02d_bk'%(index+1) + '.slc')
                outfile2 = os.path.join(slc.output, 'burst_%02d'%(index+1) + '.slc')
 
                ####Use burstnumber to look into tiff file
                ####burstNumber still refers to original burst in slice
                lineOffset = (burst.burstNumber-1) * burst.numberOfLines
                data = band.ReadAsArray(0, lineOffset, burst.numberOfSamples, burst.numberOfLines)
                datacrop = data[burst.firstValidLine:burst.lastValidLine, burst.firstValidSample:burst.lastValidSample]
 
                ######Saving the radar cross-section
                #if not os.path.isfile(outfile1):
                #    fid = open(outfile1, 'wb')
                #    outdata  = np.zeros((length,width), dtype=np.complex64)  #output radar cross-section
                #    sigmaraw = np.square(abs(datacrop))
                #    outdata[burst.firstValidLine:burst.lastValidLine, burst.firstValidSample:burst.lastValidSample] = sigmaraw
                #    outdata.tofile(fid)
                #    fid.close()
                #    ####Render ISCE XML
                #    slcImage = isceobj.createSlcImage()
                #    slcImage.setByteOrder('l')
                #    slcImage.setFilename(outfile1)
                #    slcImage.setAccessMode('read')
                #    slcImage.setWidth(width)
                #    slcImage.setLength(length)
                #    slcImage.setXmin(0)
                #    slcImage.setXmax(width)
                #    slcImage.renderHdr()
                #    burst.image = slcImage
                #else:
                #    print('File {0} already exist. Skip file output.'.format(outfile1))
    
                fid = open(outfile2, 'wb')
                outdata = np.zeros((length,width), dtype=np.complex64)  # convert to radar cross-section domain
                calicrop = np.squeeze(sigmaIntrp[burst.firstValidLine:burst.lastValidLine, burst.firstValidSample:burst.lastValidSample])
                sigmacali = np.square(abs(datacrop.real + 1j*datacrop.imag)/calicrop)
                if type == 'radio':
                    recomb = np.sqrt(sigmacali)*np.exp(1j*np.angle(datacrop))
                elif type == 'noise':  #This means radio + noise
                    noiseCrop = np.squeeze(noiseIntrp[burst.firstValidLine:burst.lastValidLine, burst.firstValidSample:burst.lastValidSample])
                    noiseCorr = noiseCrop/np.square(calicrop)
                    [ind0,ind1]   = np.where( abs(datacrop) == 0 )
                    sigmadn       = sigmacali - noiseCorr
                    sigmadn[ind0,ind1] = 0
                    [ind2,ind3]   = np.where( sigmadn < 0 )
                    sigmadn[ind2,ind3] = 1e-9  #instead of clipping at 0, assign a minimal value
                    recomb    = np.sqrt(abs(sigmadn))*np.exp(1j*np.angle(datacrop))
                outdata[burst.firstValidLine:burst.lastValidLine, burst.firstValidSample:burst.lastValidSample] = recomb
                #Skip the correction for the Elevation Antenna Pattern for now 
                outdata.tofile(fid)
                fid.close()
                ####Render ISCE XML
                slcImage = isceobj.createSlcImage()
                slcImage.setByteOrder('l')
                slcImage.setFilename(outfile2)
                slcImage.setAccessMode('read')
                slcImage.setWidth(width)
                slcImage.setLength(length)
                slcImage.setXmin(0)
                slcImage.setXmax(width)
                slcImage.renderHdr()
            src=None
            band=None
