#! /usr/bin/python3
# coding=utf-8

import os
import sys
from config import conf
from datetime import datetime
sys.path.append("../gras/Lib/site-packages")

from util.register import allowed_file, get_video_frame, run_opengait, register
from werkzeug.utils import secure_filename
from flask_toastr import Toastr
from flask import Flask, render_template, request, Response, redirect, url_for, flash, session
from pymongo import MongoClient

WORK_PATH = conf['WORK_PATH']
sys.path.append(WORK_PATH)
os.environ["CUDA_VISIBLE_DEVICES"] = conf["CUDA_VISIBLE_DEVICES"]

app = Flask(__name__)
toastr = Toastr(app)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

db = MongoClient('localhost',27017)['gras']
users = db['users']
attendance = db['attendance']

STATIC_TMP_FOLDER = conf["STATIC_TMP_FOLDER"]


@app.route('/')
def index():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():

    username = request.form['username']
    password = request.form['password']

    user = users.find_one({'username':username,'password':password})

    if user:
        session['username'] = username
        session['usertype'] = user['usertype']
        return redirect('/home')
    else:
        return redirect('/')
    
@app.route('/logout',methods=['GET'])
def logout():

    session.pop('username',None)
    session.pop('usertype',None)
    return redirect('/')



@app.route('/home',methods=['GET','POST'])
def home():
    student_attendance = []
    if session['usertype'] == 'student':
        uname = str(session['username'])
        uname = uname.capitalize()
        temp = attendance.find({'name':uname})
        for i in temp:
            student_attendance.append(i)
        return render_template("index.html",username = session['username'],usertype = session['usertype'],attend = student_attendance)
    elif session['usertype'] == 'teacher':
        temp = attendance.find()
        for i in temp:
            student_attendance.append(i)
        return render_template("index.html",username = session['username'],usertype = session['usertype'],attend = student_attendance)
    else:
        return render_template("index.html",username = session['username'],usertype = session['usertype'])

        


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    try:
        if request.method == 'POST':
            person_name = secure_filename(request.form['name'])
            vid_file = request.files['regFile']
            if person_name and vid_file and allowed_file(vid_file.filename):
                tag, message = register(person_name, vid_file)
            else:
                tag = False
                message = "Invalid name or video, please check and re-upload."

            status = 'success' if tag else 'warning'
            print(message, status)

        return redirect(url_for('home'))

    except Exception as error:
        print(error)


@app.route('/recognition', methods=['GET', 'POST'])
def gait_recognition():
    try:
        if request.method == 'POST':
            tag = False
            person_name = ""
            vid_file = request.files['recFile']
            if vid_file and allowed_file(vid_file.filename):
                tag, message = register(person_name, vid_file)
            else:
                message = "Invalid video, please check and re-upload."

            if tag:
                global name, time
                name = run_opengait()
                time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
                attendance.insert_one({'name':name,'time':time})
                return redirect('/result')
            else:
                print(message)
                return redirect('/home')

    except TypeError as error:
        print(error)

@app.route("/result")
def result():
    return render_template('components/result.html',name=name,time=time)


@app.route("/video_feed")
def video_feed():
    return Response(get_video_frame(), mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5000)
