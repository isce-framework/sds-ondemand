import json

import argparse

#Copyright 2021, by the California Institute of Technology. ALL RIGHTS RESERVED. United States Government sponsorship acknowledged. Any commercial use must be negotiated with the Office of Technology Transfer at the California Institute of Technology.</font>
#This software may be subject to U.S. export control laws and regulations. By accepting this document, the user agrees to comply with all applicable U.S. export laws and regulations. User has the responsibility to obtain export licenses, or other export authority as may be required, before exporting such information to foreign countries or providing access to foreign persons.<font>

def get_bbox(polygonString):
    polygon = json.loads(polygonString)

    coords = polygon['features'][0]['geometry']['coordinates'][0]

    minX = None
    maxX = None
    minY = None
    maxY = None
    for x,y in coords:
        if minX is None or x < minX: minX = x
        if maxX is None or x > maxX: maxX = x
        if minY is None or y < minY: minY = y
        if maxY is None or y > maxY: maxY = y

    return minX, minY, maxX, maxY


def parseArgs():
    parser = argparse.ArgumentParser(description="Find min and max (x,y) from a bounding box file produced by ariaExtract and print in SNWE order")

    parser.add_argument('-f', '--file', type=str, required=True,
                        help='bounding box file.')

    return parser.parse_args()


def main(bboxFile):

    with open(bboxFile,'r') as bb:
        bboxString = bb.read()

    return get_bbox(bboxString)


if __name__ == '__main__':
    minX,minY,maxX,maxY = main(parseArgs().file)

    print(minY,maxY,minX,maxX)
