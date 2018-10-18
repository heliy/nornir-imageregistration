'''
Created on Sep 26, 2018

@author: u0490822
'''
import unittest

import os
import pickle
import nornir_pools
import nornir_shared.plot
import nornir_shared.plot as plot
import numpy as np
import nornir_imageregistration.files
import nornir_imageregistration.transforms.meshwithrbffallback
from nornir_imageregistration.local_distortion_correction import RefineTwoImages
from nornir_imageregistration.alignment_record import EnhancedAlignmentRecord
import nornir_imageregistration.assemble

from nornir_shared.files import try_locate_file

from . import setup_imagetest
from . import test_arrange
import local_distortion_correction

# class TestLocalDistortion(setup_imagetest.TransformTestBase):
# 
#     @property
#     def TestName(self):
#         return "GridRefinement"
#     
#     def setUp(self):
#         super(TestLocalDistortion, self).setUp()
#         return 
# 
# 
#     def tearDown(self):
#         super(TestLocalDistortion, self).tearDown()
#         return
# 
# 
#     def testRefineMosaic(self):
#         '''
#         This is a test for the refine mosaic feature which is not fully implemented
#         '''
#         tilesDir = self.GetTileFullPath()
#         mosaicFile = self.GetMosaicFile("Translated")
#         mosaic = nornir_imageregistration.mosaic.Mosaic.LoadFromMosaicFile(mosaicFile)
#         mosaic.RefineMosaic(tilesDir, usecluster=False)
#         pass
    
class TestSliceToSliceRefinement(setup_imagetest.TransformTestBase, setup_imagetest.PickleHelper):

    @property
    def TestName(self):
        return "StosRefinement"
    
    def setUp(self):
        super(TestSliceToSliceRefinement, self).setUp()
        return 

    def tearDown(self):
        super(TestSliceToSliceRefinement, self).tearDown()
        return
    
    @property
    def ImageDir(self):
        return os.path.join(self.ImportedDataPath, '..\\..\\Images\\')
    
    def testStosRefinement(self):
        '''
        This is a test for the refine mosaic feature which is not fully implemented
        '''
        tilesDir = self.GetTileFullPath()
        stosFile = self.GetStosFile("0164-0162_brute_32")
        stosObj = nornir_imageregistration.files.StosFile.Load(stosFile)
        
        fixedImage = os.path.join(self.ImageDir, stosObj.ControlImageFullPath)
        warpedImage = os.path.join(self.ImageDir, stosObj.MappedImageFullPath)
        
        fixedImageData = nornir_imageregistration.core.ImageParamToImageArray(fixedImage)
        warpedImageData = nornir_imageregistration.core.ImageParamToImageArray(warpedImage)
        
        stosTransform = nornir_imageregistration.transforms.factory.LoadTransform(stosObj.Transform, 1)
        
        unrefined_image_path = os.path.join(self.TestOutputPath, 'unrefined_transform.png')
        
        if not os.path.exists(unrefined_image_path):        
            unrefined_warped_image = nornir_imageregistration.assemble.TransformStos(stosTransform, fixedImage=fixedImage, warpedImage=warpedImage)
            nornir_imageregistration.SaveImage(unrefined_image_path, unrefined_warped_image)
        else:
            unrefined_warped_image = nornir_imageregistration.LoadImage(unrefined_image_path)
        
        
        num_iterations = 8
        
        cell_size=(256, 256)
        grid_spacing=(256, 256)
        
        i = 1
        
        #finalized_points = {}
                
        while i <= num_iterations: 
                
            cachedFileName = 'alignment_points_Cell_{2}x{1}_Grid_{4}x{3}_pass{0}'.format(i,cell_size[0], cell_size[1], grid_spacing[0], grid_spacing[1])
            alignment_points = self.ReadOrCreateVariable(cachedFileName)
            
            if alignment_points is None:
                alignment_points = RefineTwoImages(stosTransform,
                            os.path.join(self.ImageDir, stosObj.ControlImageFullPath),
                            os.path.join(self.ImageDir, stosObj.MappedImageFullPath),
                            os.path.join(self.ImageDir, stosObj.ControlMaskFullPath),
                            os.path.join(self.ImageDir, stosObj.MappedMaskFullPath),
                            cell_size=cell_size,
                            grid_spacing=grid_spacing)
                self.SaveVariable(alignment_points, cachedFileName)
                
            histogram_filename = os.path.join(self.TestOutputPath, 'weight_histogram_pass{0}.png'.format(i))
            TestSliceToSliceRefinement._PlotWeightHistogram(alignment_points, histogram_filename, cutoff=1.0 - (float(i) / float(num_iterations)))
            vector_field_filename = os.path.join(self.TestOutputPath, 'Vector_field_pass{0}.png'.format(i))
            TestSliceToSliceRefinement._PlotPeakList(alignment_points, vector_field_filename)
                
            percentile = (1.0 - (i / float(num_iterations))) * 100.0
            if percentile < 5.0:
                percentile = 5.0
                
            updatedTransform = local_distortion_correction._PeakListToTransform(alignment_points, percentile)
#             
#             new_finalized_points = local_distortion_correction.CalculateFinalizedAlignmentPointsMask(alignment_points)
#             
#             for (i, record) in enumerate(alignment_points): 
#                 if not finalized_points[i]:
#                     continue
#                 
#                 finalized_points[tuple(record.FixedPoint)] =  
#                 
#             
            stosObj.Transform = updatedTransform
            stosObj.Save(os.path.join(self.TestOutputPath, "UpdatedTransform_pass{0}.stos".format(i)))
                    
            warpedToFixedImage = nornir_imageregistration.assemble.TransformStos(updatedTransform, fixedImage=fixedImageData, warpedImage=warpedImageData)
             
            Delta = warpedToFixedImage - fixedImageData
            ComparisonImage = np.abs(Delta)
            ComparisonImage = ComparisonImage / ComparisonImage.max() 
             
            nornir_imageregistration.SaveImage(os.path.join(self.TestOutputPath, 'delta_pass{0}.png'.format(i)), ComparisonImage)
            nornir_imageregistration.SaveImage(os.path.join(self.TestOutputPath, 'image_pass{0}.png'.format(i)), warpedToFixedImage)
 
            #nornir_imageregistration.core.ShowGrayscale([fixedImageData, unrefined_warped_image, warpedToFixedImage, ComparisonImage])
             
            i = i + 1
            
            stosTransform = updatedTransform
            
        pass
    
    @classmethod
    def _PlotWeightHistogram(cls, alignment_records, filename, cutoff):
        weights = np.asarray(list(map(lambda a: a.weight, alignment_records)))
        h = nornir_shared.histogram.Histogram.Init(np.min(weights), np.max(weights))
        h.Add(weights)
        nornir_shared.plot.Histogram(h, Title="Histogram of Weights", xlabel="Weight Value", ImageFilename=filename, MinCutoffPercent=cutoff, MaxCutoffPercent=1.0)
    
    @classmethod
    def _PlotPeakList(cls, alignment_records, filename):
        '''
        Converts a set of EnhancedAlignmentRecord peaks from the RefineTwoImages function into a transform
        '''
    
        FixedPoints = np.asarray(list(map(lambda a: a.FixedPoint, alignment_records)))
        OriginalWarpedPoints = np.asarray(list(map(lambda a: a.OriginalWarpedPoint, alignment_records)))
        AdjustedFixedPoints = np.asarray(list(map(lambda a: a.AdjustedFixedPoint, alignment_records)))
        AdjustedWarpedPoints = np.asarray(list(map(lambda a: a.AdjustedWarpedPoint, alignment_records)))
        weights = np.asarray(list(map(lambda a: a.weight, alignment_records)))
        WarpedPeaks = AdjustedWarpedPoints - OriginalWarpedPoints
        peaks = np.asarray(list(map(lambda a: a.peak, alignment_records)))
        
        nornir_shared.plot.VectorField(OriginalWarpedPoints, WarpedPeaks, weights, filename )
        #nornir_shared.plot.VectorField(FixedPoints, peaks, filename )
         
        return
    
    
    
    def testAlignmentRecordsToTransforms(self):
        '''
        Converts a set of alignment records into a transform
        '''
        
        InitialTransformPoints = [[0, 0, 10, 10],
                                  [10, 0, 20, 10],
                                  [0, 10, 10, 20],
                                  [10, 10, 20, 20]]
        T = nornir_imageregistration.transforms.meshwithrbffallback.MeshWithRBFFallback(InitialTransformPoints)
        
        transformed = T.InverseTransform(T.FixedPoints)
        self.assertTrue(np.allclose(T.WarpedPoints, transformed), "Transform could not map the initial input to the test correctly")
        
        transform_testPoints = [[-1,-2]] 
        expectedOutOfBounds = np.asarray([[9,8]], dtype=np.float64) 
        transformed_out_of_bounds = T.InverseTransform(transform_testPoints)
        self.assertTrue(np.allclose(transformed_out_of_bounds, expectedOutOfBounds), "Transform could not map the initial input to the test correctly")
         
        inverse_transformed_out_of_bounds = T.Transform(expectedOutOfBounds)
        self.assertTrue(np.allclose(transform_testPoints, inverse_transformed_out_of_bounds), "Transform could not map the initial input to the test correctly")
        
        #Create fake alignment results requiring us to shift the transform up one
        a = EnhancedAlignmentRecord((0,0), (0,0), (10,10), (1,0), 1.5)
        b = EnhancedAlignmentRecord((1,0), (10,0), (20,10), (1,0), 2.5)
        c = EnhancedAlignmentRecord((0,1), (0,10), (10,20), (1,0), 3)
        d = EnhancedAlignmentRecord((1,1), (10,10), (20,20), (1,0), 2)
        
        records = [a,b,c,d]
        
        ##Transforming the adjusted fixed point with the old transform generates an incorrect result
        for r in records:
            r.CalculatedWarpedPoint = T.InverseTransform(r.AdjustedFixedPoint)
        ########
        
        transform = local_distortion_correction._PeakListToTransform(records)
        
        test1 = np.asarray(((0,0),(5,5),(10,10)))
        expected1 = np.asarray(((9,10),(14,15),(19,20))) 
        actual1 = transform.InverseTransform(test1)
        
        self.assertTrue(np.allclose(expected1, actual1))
         
        records2 = []
        ####Begin 2nd pass.  Pretend we need to shift every over one
        for iRow in range(0,transform.WarpedPoints.shape[0]):
            r = EnhancedAlignmentRecord(records[iRow].ID, 
                                        transform.FixedPoints[iRow,:], 
                                        transform.WarpedPoints[iRow,:], 
                                        (0,-1),
                                        5.0)
            records2.append(r)
            
        
        transform2 = local_distortion_correction._PeakListToTransform(records2)
        test2 = np.asarray(((0,0),(5,5),(10,10)))
        expected2 = np.asarray(((9,11),(14,16),(19,21))) 
        actual2 = transform2.InverseTransform(test2)
        
        self.assertTrue(np.allclose(expected2, actual2))
        
        pass


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()