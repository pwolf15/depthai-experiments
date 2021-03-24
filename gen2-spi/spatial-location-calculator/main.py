#!/usr/bin/env python3

import cv2
import depthai as dai
import numpy as np
from time import sleep

viewDepth = False
spiOut = True
if spiOut:
    viewDepth = False

# Start defining a pipeline
pipeline = dai.Pipeline()

# Define a source - two mono (grayscale) cameras
monoLeft = pipeline.createMonoCamera()
monoRight = pipeline.createMonoCamera()
stereo = pipeline.createStereoDepth()
spatialLocationCalculator = pipeline.createSpatialLocationCalculator()

# Create output
if(viewDepth):
    xoutDepth = pipeline.createXLinkOut()
    xoutDepth.setStreamName("depth")
    stereo.depth.link(xoutDepth.input)
    spatialLocationCalculator.passthroughDepth.link(xoutDepth.input)

if spiOut:
    spiOutSpatialData = pipeline.createSPIOut()
    spiOutSpatialData.setStreamName("spimetaout")
    spiOutSpatialData.setBusId(0)
    spatialLocationCalculator.out.link(spiOutSpatialData.input)
else:
    xoutSpatialData = pipeline.createXLinkOut()
    xoutSpatialData.setStreamName("spatialData")
    spatialLocationCalculator.out.link(xoutSpatialData.input)


# MonoCamera
monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoLeft.setBoardSocket(dai.CameraBoardSocket.LEFT)
monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoRight.setBoardSocket(dai.CameraBoardSocket.RIGHT)

outputDepth = True
# Only standard mode is supported in this example.
outputRectified = False
lrcheck = False
subpixel = False

# StereoDepth
stereo.setOutputDepth(outputDepth)
stereo.setOutputRectified(outputRectified)
stereo.setConfidenceThreshold(255)

stereo.setLeftRightCheck(lrcheck)
stereo.setSubpixel(subpixel)

monoLeft.out.link(stereo.left)
monoRight.out.link(stereo.right)

stereo.depth.link(spatialLocationCalculator.inputDepth)

# can be either normalized
topLeft = dai.Point2f(0.2, 0.2)
bottomRight = dai.Point2f(0.6, 0.6)
# or absolute ATTENTION on boundaries, relative to sensor config (640x400 in this example)
# topLeft = dai.Point2f(128, 80)
# bottomRight = dai.Point2f(384, 240)

spatialLocationCalculator.setWaitForConfigInput(False)
config = dai.SpatialLocationCalculatorConfigData()
config.depthThresholds.lowerThreshold = 100
config.depthThresholds.upperThreshold = 10000
config.roi = dai.Rect(topLeft, bottomRight)
spatialLocationCalculator.initialConfig.addROI(config)


# Pipeline defined, now the device is assigned and pipeline is started
device = dai.Device(pipeline)
device.startPipeline()

# Output queue will be used to get the depth frames from the outputs defined above
if(viewDepth):
    depthQueue = device.getOutputQueue(name="depth", maxSize=4, blocking=False)
if not spiOut:
    spatialQueue = device.getOutputQueue(name="spatialData", maxSize=4, blocking=False)


while True:
    if spiOut:
        sleep(1)
        continue


    inSpatialDatas = spatialQueue.get() # blocking call, will wait until a new data has arrived
    spatialDatas = inSpatialDatas.getSpatialLocations()

    for spatialData in spatialDatas:
        roi = spatialData.config.roi
        avgDepth = spatialData.depthAverage # same as Z coordinate
        x = spatialData.spatialCoordinates.x
        y = spatialData.spatialCoordinates.y
        z = spatialData.spatialCoordinates.z
        euclideanDistance = np.sqrt(x*x + y*y + z*z)
        print(f"Euclidean distance {int(euclideanDistance)} mm, X: {int(x)} mm, Y: {int(y)} mm, Z: {int(z)} mm")

    if(viewDepth):
        depth = depthQueue.get()
        depthFrame = depth.getFrame()

        depthFrameColor = cv2.normalize(depthFrame, None, 255, 0, cv2.NORM_INF, cv2.CV_8UC1)
        depthFrameColor = cv2.equalizeHist(depthFrameColor)
        depthFrameColor = cv2.applyColorMap(depthFrameColor, cv2.COLORMAP_HOT)

        color = (255, 255, 255)
        for spatialData in spatialDatas:
            roi = spatialData.config.roi
            roi = roi.denormalize(width=depthFrameColor.shape[1], height=depthFrameColor.shape[0])
            xmin = int(roi.topLeft().x)
            ymin = int(roi.topLeft().y)
            xmax = int(roi.bottomRight().x)
            ymax = int(roi.bottomRight().y)
            
            avgDepth = spatialData.depthAverage # same as Z coordinate
            fontType = cv2.FONT_HERSHEY_TRIPLEX
            cv2.rectangle(depthFrameColor, (xmin, ymin), (xmax, ymax), color, cv2.FONT_HERSHEY_SCRIPT_SIMPLEX)
            cv2.putText(depthFrameColor, f"X: {int(spatialData.spatialCoordinates.x)} mm", (xmin + 10, ymin + 20), fontType, 0.5, color)
            cv2.putText(depthFrameColor, f"Y: {int(spatialData.spatialCoordinates.y)} mm", (xmin + 10, ymin + 35), fontType, 0.5, color)
            cv2.putText(depthFrameColor, f"Z: {int(spatialData.spatialCoordinates.z)} mm", (xmin + 10, ymin + 50), fontType, 0.5, color)


        # frame is transformed, the color map will be applied to highlight the depth info
        # frame is ready to be shown
        cv2.imshow("depth", depthFrameColor)

    if cv2.waitKey(1) == ord('q'):
        break
