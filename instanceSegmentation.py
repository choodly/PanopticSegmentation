import os
import sys
import numpy as np
import json
import yaml
from addict import Dict
from tqdm import tqdm
import cv2

from helpers import makeResultsDirectory, loadJson

mainConfig = Dict(yaml.load(open("./config.yaml")))

makeResultsDirectory(mainConfig.results_folder)

# Root directory of the project
MASK_RCNN_ROOT_DIR = os.path.abspath(mainConfig.mrcnn_path)
sys.path.append(MASK_RCNN_ROOT_DIR)

from mrcnn import utils
import mrcnn.model as modellib
from mrcnn.model import log
import samples.coco.coco as coco
from pycocotools.coco import COCO

ROOT_DIR = os.path.abspath("./")
WEIGHTS_PATH = os.path.join(ROOT_DIR, 'weights')

MODEL_DIR = os.path.join(ROOT_DIR, "logs")

COCO_MODEL_PATH = os.path.join(ROOT_DIR, mainConfig.mrcnn_weights)

# Download COCO trained weights from Releases if needed
if not os.path.exists(COCO_MODEL_PATH):
    utils.download_trained_weights(COCO_MODEL_PATH)

config = coco.CocoConfig()
# config.display()

COCO_DATA_DIR = os.path.abspath(mainConfig.coco_dir)
COCO_ANNOTATIONS_PATH = os.path.abspath(mainConfig.coco_ann_path)

dataset = coco.CocoDataset()

if mainConfig.data_set == "val2017":
    dataset.load_coco(COCO_DATA_DIR, "val", "2017")
    dataset.prepare()
else:
    raise Exception('No other datasets can be used for now. Please use val2017')

model = modellib.MaskRCNN(mode="inference", config=config, model_dir=MODEL_DIR )
model.load_weights(COCO_MODEL_PATH, by_name=True)

lim = int(mainConfig.image_limit) if mainConfig.image_limit != 'None' else None


def runPredictions(model, dataset, limit=None):

    # Checkpoint Loader
    try:
        instance_segmentation_results = loadJson('./{}/{}.json'.format(mainConfig.results_folder, mainConfig.instance_result_json))
        upToIndex = loadJson('./{}/instanceIdx.json'.format(mainConfig.results_folder))['index']
    except FileNotFoundError:
        instance_segmentation_results = []
        upToIndex = 0
        print ('No file on record, starting from the beginning')

    image_range = limit if limit is not None else len(dataset.image_info)

    for index in tqdm(range(image_range)):

        # Skip until where we left off
        if index < upToIndex:
            print ('skipping => Image index=', index, 'Progress Index=', upToIndex)
            continue

        # Checkpoint System
        if index % 50 == 0:
            with open('{}/instanceIdx.json'.format(mainConfig.results_folder), 'w') as outfile:
                json.dump({'index': index}, outfile)

            with open('{}/{}.json'.format(mainConfig.results_folder,
                    mainConfig.instance_result_json), 'w') as outfile:
                json.dump(instance_segmentation_results, outfile)

        current_image_info = dataset.image_info[index]

        image_path = current_image_info['path']
        image_id = current_image_info['id']
        image = cv2.imread(image_path)

        predictions = model.detect([image], verbose=1)
        prediction = predictions[0] # single image batch size so just accessing it

        coco_results = coco.build_coco_results(dataset,
                                        [image_id],
                                        prediction['rois'],
                                        prediction['class_ids'],
                                        prediction['scores'],
                                        prediction['masks'].astype(np.uint8))
        instance_segmentation_results.extend(coco_results)

    # Final dump of JSON
    with open('{}/{}.json'.format(mainConfig.results_folder,
            mainConfig.instance_result_json), 'w') as outfile:
        json.dump(instance_segmentation_results, outfile)

    return instance_segmentation_results

runPredictions(model, dataset, lim)
