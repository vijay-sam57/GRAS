#! /usr/bin/python3
# coding=utf-8

import os
import cv2
import json
import time
from re import search

from config import conf
from database import get_pname_from_vid
from util.pretreatment import imgs_to_pickle
from util.general import md5_file, copy_file, rename_dir_file, del_file, time_sync
from model.gait.main import opengait_main
from model.person_ext.rvm.person_ext import person_ext_rvm
from model.person_det.yolov5.detect_person import yolov5_detect_person
from database import person_register, md5_exists
from werkzeug.utils import secure_filename


WORK_PATH = conf['WORK_PATH']
ALLOWED_EXTENSIONS = conf["ALLOWED_EXTENSIONS"]
UPLOAD_FOLDER = conf["UPLOAD_FOLDER"]
DATASETS_FOLDER = conf["DATASETS_FOLDER"]
TMP_FOLDER = os.path.sep.join([UPLOAD_FOLDER, "tmp"])
STATIC_TMP_FOLDER = conf["STATIC_TMP_FOLDER"]
PROBE_FOLDER = os.path.sep.join([conf["DATASETS_FOLDER"], "probe"])
pre_method = conf["PRE_METHOD"]
frame_size_threshold = conf["ext_frame_size_threshold"]
pixel_threshold = conf["cut_img_pixel_threshold"]
global person_label
person_label = []


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() in ALLOWED_EXTENSIONS


def register(person_name, vid_file):
    del_file(TMP_FOLDER)
    del_file(STATIC_TMP_FOLDER)
    if person_name == "":
        del_file(PROBE_FOLDER)
    os.makedirs(TMP_FOLDER, exist_ok=True)

    tag = False
    filename = secure_filename(vid_file.filename)
    video_tmp_path = os.path.sep.join([TMP_FOLDER, filename])
    vid_file.stream.seek(0)
    vid_file.save(video_tmp_path)
    vid, vmd5 = md5_file(video_tmp_path)
    vname = vid + "." + filename.rsplit('.', 1)[-1].lower()

    if md5_exists(vmd5):  
        message = "Video exists, please upload another!"
    else:
        tag = True
        print()
        t1 = time_sync()
        t2, t3 = 0, 0
        print("Registration Start.")
        _, pid = person_register(person_name, vid, vmd5, vname)
        person_folder = os.path.sep.join([UPLOAD_FOLDER, pid])
        pkl_folder = os.path.sep.join([person_folder, "pkl", vid])

        frame_nums = "frame exits"
        if not os.path.exists(pkl_folder):
            video_save_path = os.path.sep.join([person_folder, 'video', vname])

            copy_file(video_tmp_path, video_save_path)

            # print()
            t2 = time_sync()
            print("Pretreatment Start.")
            if pre_method == "rvm":
                person_ext_rvm(vid, video_save_path, person_folder, frame_size_threshold)
                t3 = time_sync()

                save_cut_img = True if pid == "probe" else False
                frame_nums = imgs_to_pickle(vid, person_folder, save_cut_img, pixel_threshold)

        if frame_nums:
            # move pkl to datasets
            dataset_folder = os.path.sep.join([DATASETS_FOLDER, pid, vid])
            copy_file(pkl_folder, dataset_folder)

            if pid == "probe":
                person_cut_img = os.path.sep.join([person_folder, "cut_img", vid])
                static_cut_img = os.path.sep.join([STATIC_TMP_FOLDER, "cut_img"])
                copy_file(person_cut_img, static_cut_img)

                person_image = os.path.sep.join([person_folder, "image", vid])
                static_image = os.path.sep.join([STATIC_TMP_FOLDER, "image"])
                copy_file(person_image, static_image)
                rename_dir_file(static_image)  # avoid http web cache problem

            message = f"person name: {person_name} pid: {pid} video name: {filename} vid: {vid} valid frame: {frame_nums}"
        else:
            tag = False
            message = f"{vid}: no valid data."

        t4 = time_sync()
        print(message)
        print("Done! Registration and Pretreatment are complete.")
    return tag, message


def run_opengait():
    print()
    t1 = time_sync()
    print("Recognition Start.")
    global person_label
    person_label_exists = False

    res = opengait_main()
    os.chdir(WORK_PATH)

    for i in res:
        for j in list(res[i]):
            vid = j.split("-")[-1]
            pname = get_pname_from_vid(vid)
            label = pname + "-" + vid

            res[i][label] = res[i].pop(j)
            if not person_label_exists and res[i][label]["similarity"] > 0.5:
                person_label.append(pname + ' {:.2f}%'.format(100*res[i][label]["similarity"]))
                person_label_exists = True

    res = "data: " + json.dumps(res[i]) + "\n\n"
    t2 = time_sync()
    global name
    name = search('[a-zA-Z]+',str(person_label)).group()
    print(name)
    return name


def get_video_frame():
    global person_label
    video_path = os.path.sep.join([TMP_FOLDER, os.listdir(TMP_FOLDER)[0]])
    video = cv2.VideoCapture(video_path)
    fps = video.get(cv2.CAP_PROP_FPS)
    label = ''
    while video.isOpened():
        ret, frame = video.read()
        if not ret:
            break

        if not label and name:
            label = name
        frame = yolov5_detect_person(frame, label)

        (flag, encodedImage) = cv2.imencode(".jpg", frame)
        if not flag:
            continue

        frame = b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n'
        yield frame

    video.release()
