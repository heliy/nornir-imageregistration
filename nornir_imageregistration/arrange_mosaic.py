'''
Created on Jul 10, 2012

@author: Jamesan
'''
 
from operator import attrgetter
import os
import numpy as np
import scipy.spatial
import itertools
import math
 
import nornir_imageregistration.spatial as spatial 
import nornir_imageregistration.core as core
import nornir_imageregistration.tileset as tileModule 
import nornir_imageregistration.tileset as tileset
import nornir_imageregistration.tile
import nornir_imageregistration.layout
from nornir_imageregistration.alignment_record import AlignmentRecord

import nornir_pools


def TranslateTiles(transforms, imagepaths, imageScale=None):
    '''
    Finds the optimal translation of a set of tiles to construct a larger seemless mosaic.
    '''

    tiles = nornir_imageregistration.layout.CreateTiles(transforms, imagepaths)

    if imageScale is None:
        imageScale = tileModule.MostCommonScalar(transforms, imagepaths)

    offsets_collection = _FindTileOffsets(tiles, imageScale)
    
    final_layout = nornir_imageregistration.layout.BuildLayoutWithHighestWeightsFirst(offsets_collection)

    # Create a mosaic file using the tile paths and transforms
    return (final_layout, tiles)


def _CalculateImageFFTs(tiles):
    '''
    Ensure all tiles have FFTs calculated and cached
    '''
    pool = nornir_pools.GetLocalMachinePool()
     
    fft_tasks = [] 
    for t in tiles.values(): 
        task = pool.add_task("Create padded image", t.PrecalculateImages)
        task.tile = t
        fft_tasks.append(task)
        
    print("Calculating FFTs\n")
    pool.wait_completion()
    
    
def _FindTileOffsets(tiles, imageScale=None):
    '''Populates the OffsetToTile dictionary for tiles
    :param dict tiles: Dictionary mapping TileID to a tile
    :param dict imageScale: downsample level if known.  None causes it to be calculated.'''

    if imageScale is None:
        imageScale = 1.0
        
    downsample = 1.0 / imageScale

    #idx = tileset.CreateSpatialMap([t.ControlBoundingBox for t in tiles], tiles)

    CalculationCount = 0
    
    #_CalculateImageFFTs(tiles)
 
    pool = nornir_pools.GetLocalMachinePool()
    tasks = list()
    
    layout = nornir_imageregistration.layout.Layout()
    for t in tiles.values():
        layout.CreateNode(t.ID, t.ControlBoundingBox.Center)
      
    for A,B in __iterateOverlappingTiles(tiles):
        t = pool.add_task("Align %d -> %d %s", __tile_offset, A, B, imageScale)
        t.A = A
        t.B = B
        tasks.append(t) 
        CalculationCount += 1
        print("Start alignment %d -> %d" % (A.ID, B.ID))

    for t in tasks:
        offset = t.wait_return()
        
        #Figure out what offset we found vs. what offset we expected
        PredictedOffset = t.B.ControlBoundingBox.Center - t.A.ControlBoundingBox.Center
        ActualOffset = offset.peak * downsample
        
        diff = ActualOffset - PredictedOffset
        distance = np.sqrt(np.sum(diff ** 2))
        
        print("%d -> %d = %g" % (t.A.ID, t.B.ID, distance))
        
        layout.SetOffset(t.A.ID, t.B.ID, offset.peak * downsample, offset.weight) 
    
    print(("Total offset calculations: " + str(CalculationCount)))

    return layout

def __get_overlapping_imagespace_rect_for_tile(tile_obj, overlapping_rect):
    ''':return: Rectangle describing which region of the tile_obj image is contained in the overlapping_rect from volume space'''
    image_space_points = tile_obj.Transform.InverseTransform(overlapping_rect.Corners)    
    return spatial.BoundingPrimitiveFromPoints(np.round(image_space_points))

def __get_overlapping_image(image, overlapping_rect, excess_scalar=1.5):
    '''
    Crop the tile's image so it contains the specified rectangle
    '''
    
    scaled_rect = spatial.Rectangle.CreateFromBounds(np.around(spatial.Rectangle.scale(overlapping_rect, excess_scalar).ToArray()))
    return core.CropImage(image,Xo=int(scaled_rect.BottomLeft[1]), Yo=int(scaled_rect.BottomLeft[0]), Width=int(scaled_rect.Width), Height=int(scaled_rect.Height), cval='random')
    
    #return core.PadImageForPhaseCorrelation(cropped, MinOverlap=1.0, PowerOfTwo=True)
   

def __tile_offset(A,B, imageScale):
    '''
    First crop the images so we only send the half of the images which can overlap
    '''
    
    overlapping_rect = spatial.Rectangle.overlap_rect(A.ControlBoundingBox,B.ControlBoundingBox)
    
    overlapping_rect_A = __get_overlapping_imagespace_rect_for_tile(A, overlapping_rect)
    overlapping_rect_B = __get_overlapping_imagespace_rect_for_tile(B, overlapping_rect)
    
    downsampled_overlapping_rect_A = spatial.Rectangle.CreateFromBounds(np.around(overlapping_rect_A.ToArray() * imageScale))
    downsampled_overlapping_rect_B = spatial.Rectangle.CreateFromBounds(np.around(overlapping_rect_B.ToArray() * imageScale))
    ImageA = __get_overlapping_image(A.Image, downsampled_overlapping_rect_A)
    ImageB = __get_overlapping_image(B.Image, downsampled_overlapping_rect_B)
    
    #core.ShowGrayscale([ImageA, ImageB])
    #If the predicted alignment is perfect this is the offset we could have
    OffsetAdjustment = (B.ControlBoundingBox.Center - A.ControlBoundingBox.Center) * imageScale
      
    record = core.FindOffset( ImageA, ImageB, FFT_Required=True)
    adjusted_record = AlignmentRecord(np.array(record.peak) + OffsetAdjustment, record.weight)
    return adjusted_record

def __iterateOverlappingTiles(tiles, minOverlap = 0.05):
    
    for (A,B) in itertools.combinations(tiles.values(), 2):
        if spatial.rectangle.Rectangle.overlap(A.ControlBoundingBox, B.ControlBoundingBox) >= minOverlap:
            yield (A,B)

def TranslateFiles(fileDict):
    '''Translate Images expects a dictionary of images, their position and size in pixel space.  It moves the images to what it believes their optimal position is for alignment 
       and returns a dictionary of the same form.  
       Input: dict[ImageFileName] = [x y width height]
       Output: dict[ImageFileName] = [x y width height]'''

    # We do not want to load each image multiple time, and we do not know how many images we will get so we should not load them all at once.
    # Therefore our first action is building a matrix of each image and their overlapping counterparts
    return 


if __name__ == '__main__':
    pass