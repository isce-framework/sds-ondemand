"""Multi-function module for loading track frame databases,
augmenting them with NISAR observation data, saving said
databases, reloading them, and displaying them as interactable
folium maps.
"""
from datetime import datetime, timedelta
import glob
import math
import os
import time
import xml.etree.ElementTree as ET

import fiona
import geopandas as gpd
from geopandas.io.file import to_file
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
from zipfile import ZipFile


# Required to fix an issue with reading KML files
fiona.drvsupport.supported_drivers["LIBKML"] = "rw"
fiona.drvsupport.supported_drivers["KML"] = "rw"

# Statically defined radar modes dictionary
RADAR_MODES = {
    "064": ["S_37_DH_37_DV"],
    "065": ["S_10_DH_00_NA"],
    "066": ["S_10_DV_00_NA"],
    "067": ["S_25_CP_00_NA"],
    "068": ["S_37_DH_00_NA"],
    "069": ["S_37_CP_00_NA"],
    "070": ["S_25_SH_00_NA"],
    "071": ["S_25_SV_00_NA"],
    "072": ["S_75_SH_00_NA"],
    "073": ["S_75_SV_00_NA"],
    "074": ["S_37_DV_00_NA"],
    "076": ["S_37_RH_00_NA"],
    "086": ["S_10_DH_00_NA"],
    "087": ["S_10_DV_00_NA"],
    "088": ["S_25_CP_00_NA"],
    "089": ["S_37_DH_00_NA"],
    "090": ["S_37_CP_00_NA"],
    "091": ["S_25_SH_00_NA"],
    "092": ["S_25_SV_00_NA"],
    "093": ["S_75_SH_00_NA"],
    "094": ["S_75_SV_00_NA"],
    "095": ["S_37_DV_00_NA"],

    "106": ["cal"],
    "107": ["cal"],
    "108": ["cal"],
    "109": ["cal"],
    "110": ["cal"],
    "111": ["cal"],
    "112": ["cal"],
    "113": ["cal"],
    "114": ["cal"],

    "128":["L_20_DH_05_DH"],
    "129":["L_20_DH_05_DV"],
    "131":["L_80_SH_00_NA"],
    "132":["L_40_SH_05_SH"],
    "133":["L_20_SH_05_SH"],
    "134":["L_05_SV_00_NA"],
    "135":["L_05_QD_00_NA"],
    "136":["L_20_DV_05_DV"],
    "137":["L_40_DH_05_DH"],
    "138":["L_40_DH_05_DV"],
    "140":["L_40_QP_05_QP"],
    "141":["L_20_QP_05_QP"],
    "142":["L_20_CR_20_CR"],
    "143":["L_20_DH_20_DV"],
    "144":["L_80_SH_00_NA"],
    "145":["L_05_DV_00_NA"],
    "146":["L_05_QQ_00_NA"],
    "178":["L_20_DH_05_DH"],

    "179":["cal"],
    "180":["cal"],
    "187":["cal"],
    "188":["cal"],
    "189":["cal"],
    "190":["cal"],
    "191":["cal"],

    "192":["L_20_DH_05_DH","S_25_CP_00_NA"],
    "195":["L_05_SV_00_NA","S_10_DV_00_NA"],
    "196":["L_20_DV_05_DV","S_25_CP_00_NA"],
    "197":["L_40_DH_05_DH","S_37_CP_00_NA"],
    "199":["L_40_QP_05_QP","S_75_SH_00_NA"],
    "205":["L_80_SH_00_NA","S_25_CP_00_NA"],
    "206":["L_20_DH_05_DH","S_25_SV_00_NA"],
    "207":["L_40_DH_05_DH","S_75_SV_00_NA"],
    "232":["L_05_SV_00_NA","S_05_CP_00_NA"],
    "238":["L_40_DH_05_DH","S_37_DH_00_NA"],
    "240":["L_20_DH_05_DV", "S_25_DH_00_NA"],
    "241":["L_20_DH_05_DH","S_25_DH_00_NA"],
    "242":["L_40_DH_05_DH","S_25_DH_00_NA"],
    "243":["L_40_DH_05_DV","S_25_DH_00_NA"],
    "244":["L_40_QP_05_QP","S_25_DH_00_NA"],
    "245":["L_20_QP_05_QP","S_25_DH_00_NA"],
    "246":["L_80_SH_00_NA","S_37_SH_00_NA"],
    "247":["L_40_SH_05_SH", "S_37_SH_00_NA"],
    "254":["Post-Take-Joint"],
    "255":["Pre-Take-Joint"],
}

# Extracted list of 80 MHz radar modes from the modes dictionary
HALF_FRAME_MODES = []
for mode_key, value_list in RADAR_MODES.items():
    for val in value_list:
        if val.startswith("L_80"):
            HALF_FRAME_MODES.append(mode_key)
            break


# Eval functions from copied from SDS PCM
def convert_datetime(datetime_obj, strformat="%Y-%m-%dT%H:%M:%S.%f"):
    """Converts from a datetime string to a datetime object
    or vice versa.
    """
    if isinstance(datetime_obj, datetime):
        return datetime_obj.strftime(strformat)
    return datetime.strptime(str(datetime_obj), strformat)


def to_datetime(input_object, strformat="%Y-%m-%dT%H:%M:%S.%f"):
    """Takes as input either a datetime object or an ISO datetime string
    in UTC and returns a datetime object.
    """
    if isinstance(input_object, str):
        return convert_datetime(input_object, strformat)
    if not isinstance(input_object, datetime.datetime):
        raise ValueError("Do not know how to convert type {} to datetime".format(
                         str(type(input_object))))
    return input_object


def get_track_frames_for_one_cycle(
        ctz_utc: str,
        start_time_utc: datetime,
        end_time_utc: datetime,
        tfdb,strformat="%Y-%m-%dT%H:%M:%S.%f"):
    """
    Queries the track frame database for records that partially or fully overlap
    with the given time range. Returns all records that overlap.
    Returns:
        A GeoDataFrame object containing the track frame records from
        the Track Fame Database that partially or fully overlap with the given
        start and end time, with the following additional columns:
            cycle           Cycle ID
            start_time_utc  Start time in UTC of the track frame
            end_time_utc    End time in UTC of the track frame
    :param cycle_info: Data for the cycle
    :param start_time_utc: Start of the time range in UTC
    :param end_time_utc: End of the time range in UTC
    :param tfdb_filename: Track frame database filename
    :return: GeoDataFrame object
    """
    start_seconds_since_ctz = (start_time_utc - ctz_utc).total_seconds()
    end_seconds_since_ctz = (end_time_utc - ctz_utc).total_seconds()
    
    results = tfdb[(end_seconds_since_ctz >= tfdb.startCY)
                   & (tfdb.endCY >= start_seconds_since_ctz)]
    return results


def cross_product(a: shapely.Point, b: shapely.Point, c: shapely.Point):
    """Computes whether c lies to one side of the line formed by
    a and b or to the other.
    """
    if not isinstance(a, type(c)) or not isinstance(b, type(c)):
        if any(isinstance(x, shapely.Point) for x in [a, b, c]):
            raise Exception(f"{type(a)=} or {type(b)=} is not equal to {type(c)=}")
    (a_x, a_y) = (a.x, a.y) if isinstance(a, shapely.Point) else (a[0], a[1])
    (b_x, b_y) = (b.x, b.y) if isinstance(b, shapely.Point) else (b[0], b[1])
    (c_x, c_y) = (c.x, c.y) if isinstance(c, shapely.Point) else (c[0], c[1])
    return (c_x - a_x)*(b_y - a_y) - (c_y - a_y)*(b_x - a_x)


def get_centroid_list(multipolygon: shapely.MultiPolygon) -> list:
    """Returns the list of centroids in a multipolygon and a list
    of its transposed coordinates as lists.
    """
    centroid_list = []
    coord_list = []
    for polygon in list(multipolygon.geoms):
        centroid_list.append(polygon.centroid)
        coord_list.append([polygon.centroid.y, polygon.centroid.x])
    return centroid_list, coord_list


def plot_point(m: object, p: list | shapely.Point, color: str=None, tag: str=None):
    """Plots a point on the folium map given by m."""
    loc = [p.y, p.x] if isinstance(p, shapely.Point) else [p[1], p[0]]
    color = "red" if color is None else color
    folium.Marker(
        location=loc,
        popup=tag,
        icon=folium.Icon(color=color)
    ).add_to(m)


def write_to_gpkg(track_frame, outPath):
    ##First track to be written uses this mode.
    ##Is reset later to append on first write.
    gpkgWriteMode = "w"
  
    for track in range(track_frame.track.min(), track_frame.track.max()+1):
        gdf = track_frame.query("track=={}".format(track))
        to_file(gdf, outPath, layer="T{0:03d}".format(track), driver="GPKG")
        gpkgWriteMode="a"


def isnan(value):
    """Checks whether the input value is nan."""
    try:
        return np.isnan(value)
    except:
        return False
    
    
class TrackFrameAnalyzer:
    """Class for managing track frame dataframes loaded by pandas."""
    strformat = "%Y-%m-%dT%H:%M:%S.%f"
    obs_strformat = f"{strformat}Z"
    augmented_cols = {
        "radar_mode",
        "radar_mode_name",
        "mixed_mode",
        "half_frame_mode",
        "number_of_modes",
        "observation_data_ratio",
        "time_coverage",
        "data_loss_display",
        "data_product_display",
        "data_mode_display"
    }

    def __init__(self,
                 track_frame_fname: str=None,
                 observation_data_fname: str=None,
                 ctz_times: list=None,
                 split_half_frames: bool=True):
        # Default constructor
        self.df = None
        self.augmented = False
        self.split_half_frames = False
        if track_frame_fname is None or observation_data_fname is None:
            return
        
        # Parse arguments otherwise
        _, exten = os.path.splitext(observation_data_fname)
        if exten != ".kml":
            raise ValueError(f"Cannot read non-KML file {observation_data_fname} with extention {exten}.")

        self.df = gpd.read_file(track_frame_fname)
        self.df.crs = "EPSG:4326"
        # Assign the backup geometry by copy
        self.df["backup_geometry"] = self.df["geometry"].copy()
        
        self.observations = gpd.GeoDataFrame()
        for layer in fiona.listlayers(observation_data_fname):
            try:
                #print(layer.split()[0])
                s = gpd.read_file(observation_data_fname, driver="KML", layer=layer)
                s["passDirection"] = layer.split()[0]

                radar_modes = []
                start_times = []
                stop_times = []
                radar_modes_name = []
                for decription in s["Description"]:
                    radar_mode = decription.split()[1].split("=")[1].split("conf")[1]
                    radar_modes.append(radar_mode)
                    radar_modes_name.append(RADAR_MODES[radar_mode][0])

                    start_time_str = decription.split()[4]
                    start_times.append(to_datetime(start_time_str,strformat=TrackFrameAnalyzer.obs_strformat))

                    stop_time_str = decription.split()[7]
                    stop_times.append(to_datetime(stop_time_str,strformat=TrackFrameAnalyzer.obs_strformat))

                s["radar_mode"] = radar_modes
                s["radar_mode_name"] = radar_modes_name
                s["start_times"] = start_times
                s["stop_times"] = stop_times
                self.observations = pd.concat([self.observations, s], ignore_index=True)
            except Exception as e:
                print(f"Skip {layer}: {e}")
        if ctz_times is not None:
            self.augment_df(ctz_times)
            
        if self.augmented and split_half_frames:
            self.split_geometry()


    def augment_df(self,
                   ctz_times: list,
                   coverage_threshold: float=0.15,
                   time_threshold: float=None):
        """Augments the dataframe with extra statistics.
        
        ctz_times: 1D array-like of cycle zero times. MUST be sorted beforehand.
        
        coverage_threshold: The ratio of data coverage a track frame must have to generate
        a data product. Overriden by time_threshold if the latter is specified.
        
        time_threshold: The minimum amount of observation time a track frame must have to
        generate a data product. Overrides coverage_threshold if specified.
        """
        # adding few more fields to the track-frame 
        self.df["radar_mode"] = pd.Series(dtype=int)
        self.df["radar_mode_name"] = pd.Series(dtype=str)
        self.df["mixed_mode"] = pd.Series(dtype=bool)
        self.df["half_frame_mode"] = pd.Series(dtype=bool)
        self.df["number_of_modes"] = pd.Series(dtype=int)
        self.df["observation_data_ratio"] = pd.Series(dtype=float)
        self.df["time_coverage"] = pd.Series(dtype=float)
        
        self.df["mixed_mode"] = False
        self.df["half_frame_mode"] = False
        self.df["number_of_modes"] = 0
        self.df["observation_data_ratio"] = 0
        self.df["time_coverage"] = 0

        start = time.time()
        # Looping over all rows of the observation plan, based on observation strat/stop times, determine
        # the track and frames, and populate the observation related fields for those frames
        for row in self.observations.itertuples():
            if row.radar_mode_name == "cal":
                continue

            czt_index = np.max(np.searchsorted(ctz_times, row.start_times) - 1, 0)
            cycle_zero_time = czt_sorted[czt_index]

            results = get_track_frames_for_one_cycle(
               cycle_zero_time,
                row.start_times,
                row.stop_times,
                self.df)

            sdt = (row.start_times - cycle_zero_time).total_seconds()
            edt = (row.stop_times - cycle_zero_time).total_seconds()
            for i in results.index:
                if isnan(self.df.at[i, "radar_mode"]):
                    # this frame does not have any observation so far. Let"s assign observation to this frame
                    self.df.at[i,"radar_mode"] = row.radar_mode
                    self.df.at[i,"radar_mode_name"] = row.radar_mode_name
                    self.df.at[i,"number_of_modes"] = 1
                else:
                    # looks like this frame is a mixed mode frame and already has observation. 
                    self.df.at[i,"mixed_mode"] = True
                    self.df.at[i,"number_of_modes"] = self.df.at[i,"number_of_modes"] + 1
                # If at least one radar mode is a half frame mode, mark it as so
                if row.radar_mode in HALF_FRAME_MODES:
                    self.df.at[i, "half_frame_mode"] = True

                # Looks like we need to add a column to this crap...
                ratio = self.df.at[i, "observation_data_ratio"]
                st = self.df.at[i, "startCY"]
                et = self.df.at[i, "endCY"]
                dur = et - st
                toadd = 1

                if st <= sdt <= et:
                    toadd -= (sdt - st) / dur
                if st <= edt <= et:
                    toadd -= (et - edt) / dur
                observation_data_ratio = ratio + toadd
                self.df.at[i, "observation_data_ratio"] = observation_data_ratio
                self.df.at[i, "time_coverage"] = observation_data_ratio * dur
        # Assign whether this column has a data product based on coverage or time thresholds
        if time_threshold is not None:
            self.df = self.df.assign(has_data_product=lambda x: x.time_coverage > time_threshold)
        else:
            self.df = self.df.assign(has_data_product=lambda x: x.observation_data_ratio > coverage_threshold)

        # Indicates whether a track frame has no data (0), or if it does, whether it generates a data product (1)
        self.df["data_loss_display"] = pd.Series(dtype=int)
        self.df["data_loss_display"] = 0
        self.df.loc[self.df["has_data_product"], "data_loss_display"] = 1
        self.df.loc[~(self.df["has_data_product"]) &\
                             (self.df["observation_data_ratio"] > 0), "data_loss_display"] = -1

        # Displays the number of modes per track frame while setting lost track frames to -1
        self.df["data_product_display"] = pd.Series(dtype=int)
        self.df["data_product_display"] = self.df.number_of_modes
        self.df.loc[self.df["data_loss_display"] == -1, "data_product_display"] = -1

        # Same as above, for radar mode instead. The lost track frames are indicated by math.inf
        self.df["data_mode_display"] = pd.Series(dtype=int)
        self.df["data_mode_display"] = self.df.radar_mode
        self.df.loc[self.df["data_loss_display"] == -1, "data_mode_display"] = math.inf
        
        # Mark this dataframe as augmented.
        self.augmented = True
        
        # Print the elapsed time for 
        diff = time.time() - start
        print(f"Dataframe augmented in {diff*1000} ms")
        
    def explore_lost_tracks(self, column: str="time_coverage", direction: str=None) -> object:
        """Returns an interactive folium.folium.Map of the track frames lost due to the threshold
        limits previously specified to the call to augment_df.
        
        If the dataframe was not augmented beforehand, this function will return None.
        """
        if not self.augmented:
            raise ValueError("Dataframe was not augmented before calling explore.")
        
        to_plot = self.df[self.df.data_loss_display == -1]
        if direction is not None:
            to_plot = to_plot.query(f"passDirection=='{direction}'")
        return to_plot.explore(
            column=column,
            tooltip=["track", "frame", "radar_mode", "radar_mode_name", "number_of_modes",
                     "observation_data_ratio", "has_data_product", "time_coverage"],
            popup=True
        )
    
    def explore_half_frames(self, column: str="radar_mode", direction: str=None) -> object:
        """Returns an interactive folium.folium.Map of the track frames that has
        an 80 MHz radar mode as at least one of its radar modes.
        
        If the dataframe was not augmented beforehand, this function will return None.
        """
        if not self.augmented:
            raise ValueError("Dataframe was not augmented before calling explore.")
        
        to_plot = self.df[self.df.half_frame_mode == True]
        if direction is not None:
            to_plot = to_plot.query(f"passDirection=='{direction}'")
        return to_plot.explore(
            column=column,
            tooltip=["track", "frame", "radar_mode", "radar_mode_name", "number_of_modes",
                     "has_data_product", "half_frame_mode"],
            popup=True
        )
    
    def save_data(self, filename: str):
        """Saves the GeoDataFrame database (the track frame database augmented with
        observation data columns to the specified filename.
        """
        self.df.to_file(filename)
        
    def restore_geometry(self):
        """Restores the original geometry."""
        self.df["geometry"] = self.df["backup_geometry"].copy()
        self.split_half_frames = False
        
    def split_geometry(self):
        """Splits the geometry into left and right halves."""
        for track_num in set(self.df.track):
            # Filter the frames the same track and sort by frame number
            track_frames = self.df[self.df.track == track_num].sort_values("frame")
            if len(track_frames) < 2:
                continue
                raise Exception(f"There are less than 2 frames {len(track_frames)} in Track {track_num}.")

            # Set the first reference centroid to be the second centroid
            prev_centroid_list, prev_coord_list = get_centroid_list(track_frames.iloc[1].geometry)
            for i, frame in enumerate(track_frames.itertuples()):
                curr_centroid_list, curr_coord_list = get_centroid_list(frame.geometry)
                # Skip if this is not a half radar mode
                if not frame.half_frame_mode:
                    prev_centroid_list, prev_coord_list = curr_centroid_list, curr_coord_list
                    continue

                to_add = []
                for j, polygon in enumerate(list(frame.geometry.geoms)):
                    if j >= len(prev_centroid_list):
                        to_add.append(polygon)
                        continue

                    prev_centroid = prev_centroid_list[j]
                    prev_coord = prev_coord_list[j]
                    curr_centroid = curr_centroid_list[j]
                    curr_coord = curr_coord_list[j]

                    # Assemble lists for each side a point will fall under
                    poly_a = []
                    poly_b = []
                    for point in shapely.get_coordinates(polygon):
                        cross_value = cross_product(prev_coord, curr_coord, [point[1], point[0]])
                        side_bool = cross_value > 0
                        if i == 0:
                            side_bool = not side_bool

                        if cross_value < 0.2 * shapely.Point.distance(prev_centroid, curr_centroid):
                            poly_a.append(point)
                            poly_b.append(point)
                        elif side_bool:
                            poly_a.append(point)
                        else:
                            poly_b.append(point)

                    # Convert point lists into a polygon and compare centroids to determine which one is to the right
                    try:
                        poly_a = shapely.Polygon(poly_a)
                        poly_b = shapely.Polygon(poly_b)

                        if poly_a.centroid.x < poly_b.centroid.x:
                            left, right = poly_a, poly_b
                        else:
                            left, right = poly_b, poly_a

                        # Nest polygon into a multipolygon for display purposes
                        if frame.passDirection == "Ascending":
                            # Take eastwards for ascending
                            to_add.append(right)
                        elif frame.passDirection == "Descending":
                            # Take westwards for descending
                            to_add.append(left)
                        else:
                            raise Exception(f"Encountered unknown pass direction '{frame.passDirection}'.")
                    except Exception as e:
                        print(e)
                        print(f"{poly_a=}")
                        print(f"{poly_b=}")
                try:
                    self.df.at[frame.Index, "geometry"] = shapely.MultiPolygon(to_add)
                except Exception as e:
                    print(f"Encountered exception while setting geometry: {e}")

                prev_centroid_list, prev_coord_list = curr_centroid_list, curr_coord_list
        self.split_half_frames = True
        
    @staticmethod
    def load_data(track_frame_fname: str, split_half_frames: bool=True):
        """Loads a previously augmented GeoDataFrame database (the track frame database
        augmented with observation data columns to the specified filename.
        """
        ret = TrackFrameAnalyzer()
        ret.df = gpd.read_file(track_frame_fname)
        ret.crs = "EPSG:4326"
        # Assign the backup geometry by copy
        ret.df["backup_geometry"] = ret.df["geometry"].copy()
        #gpd.io.file.fiona.drvsupport.supported_drivers["KML"] = "rw"
        ret.augmented = TrackFrameAnalyzer.augmented_cols.issubset(ret.df.columns)
        if ret.augmented and split_half_frames:
            ret.split_geometry()
        return ret
        
    @staticmethod
    def inflate_kmz(filename: str, dest: str=None) -> str:
        """Inflates the KMZ file given by filename and extracts all of its
        contents to the directory dest. Expect undefined behavior if dest
        is not empty.
        
        Returns the contents of the directory dest after inflating.
        """
        abs_fname = os.path.abspath(filename)
        if dest is None:
            dest = os.path.splitext(abs_fname)[0]
        if not os.path.isdir(dest):
            os.makedirs(dest)

        kmz = ZipFile(abs_fname, "r")
        kmz.extractall(path=dest)

        return [os.path.join(dest, dest_file) for dest_file in os.listdir(dest)]
    
    @staticmethod
    def get_czt_list(filename: str) -> np.array:
        """Retrieves the list of cycle zero times from the STUF file
        specified by filename.
        """
        tree = ET.parse(filename)
        root = tree.getroot()
        cycle_zero_times = []
        fixed_states = root.find("fixedStates")
        for state_node in fixed_states.findall("state"):
            label = state_node.find("label")
            if label is None or label.text != "SDS cycle reference":
                continue
            for time_node in state_node.findall("time"):
                if time_node.attrib.get("sys") == "UTC":
                    utc_time = to_datetime(time_node.text[:-3], strformat=TrackFrameAnalyzer.strformat)
                    cycle_zero_times.append(utc_time)
        return np.sort(cycle_zero_times)
