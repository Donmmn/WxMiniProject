# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, send_from_directory, redirect, url_for, jsonify
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from werkzeug.utils import secure_filename
from flask_cors import CORS
from io import BytesIO
from PIL import Image
import cv2
import numpy as np
import imageio
from wand.image import Image
import logging

app = Flask(__name__)
CORS(app)  # 启用CORS支持

# 设置 UTF-8 编码
app.config['JSON_AS_ASCII'] = False  # 确保 JSON 响应使用 UTF-8
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'

# 设置上传文件的存储路径
UPLOAD_FOLDER = 'Flask_Data'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 设置上传文件的最大大小为100MB
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# 设置压缩阈值为50MB
app.config['COMPRESS_THRESHOLD'] = 50 * 1024 * 1024

# 设置上传文件的扩展名
app.config['UPLOAD_EXTENSIONS'] = ['.png', '.jpg', '.jpeg', '.gif']

# 设置超时时间为5分钟
app.config['TIMEOUT'] = 300

#def allowed_file(filename):
#    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS and \
           os.path.splitext(filename)[1] in app.config['UPLOAD_EXTENSIONS']

def compress_image(file, max_size=10*1024*1024, quality=85):
    """使用 wand 压缩图片文件"""
    try:
        # 读取图片
        with Image(file=file) as img:
            # 如果图片尺寸过大，按比例缩小
            if img.width > 2000 or img.height > 2000:
                ratio = min(2000 / img.width, 2000 / img.height)
                img.resize(int(img.width * ratio), int(img.height * ratio))
            
            # 将图片保存到内存中
            output = BytesIO()
            img.format = 'jpeg'
            img.compression_quality = quality
            img.save(file=output)
            output.seek(0)
            return output.getvalue()
    except Exception as e:
        raise Exception(f'Image compression failed: {str(e)}')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file selected'
        file = request.files['file']
        if file.filename == '':
            return 'No file selected'
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # 生成新的文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_filename = f"{timestamp}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
            return redirect(url_for('upload_file'))
    return render_template('upload.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/gallery')
def gallery():
    files = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if allowed_file(filename):
            # 获取文件的原始名称和上传时间
            parts = filename.split('_', 1)
            if len(parts) == 2:
                timestamp = parts[0]
                original_name = parts[1]
                try:
                    # 尝试解析上传时间
                    upload_time = datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        # 尝试解析仅包含日期的上传时间
                        upload_time = datetime.strptime(timestamp, '%Y%m%d').strftime('%Y-%m-%d')
                    except ValueError:
                        # 解析失败，使用文件名作为上传时间
                        upload_time = "Unknown time"
                
                files.append({
                    'filename': filename,
                    'original_name': original_name,
                    'upload_time': upload_time
                })
    return render_template('gallery.html', files=files)

@app.route('/wxapp/upload', methods=['POST'])
def wxapp_upload():
    try:
        logging.debug('Received upload request')
        if 'file' not in request.files:
            logging.error('No file selected')
            return jsonify({
                'code': 400,
                'msg': 'No file selected',
                'data': None
            })
        
        file = request.files['file']
        logging.debug(f'File received: {file.filename}')
        if file.filename == '':
            return jsonify({
                'code': 400,
                'msg': 'No file selected',
                'data': None
            })

        # 检查文件大小
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)
        if file_length > app.config['MAX_CONTENT_LENGTH']:
            return jsonify({
                'code': 400,
                'msg': f'File size exceeds the limit (max {app.config["MAX_CONTENT_LENGTH"] / 1024 / 1024}MB)',
                'data': None
            })
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_filename = f"{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            
            # 如果文件大小超过压缩阈值，进行压缩
            if file_length > app.config['COMPRESS_THRESHOLD']:
                try:
                    compressed_file = compress_image(file)
                    with open(file_path, 'wb') as f:
                        f.write(compressed_file)
                except Exception as e:
                    logging.error(f'Compression failed: {str(e)}')
                    return jsonify({
                        'code': 500,
                        'msg': f'File compression failed: {str(e)}',
                        'data': None
                    })
            else:
                try:
                    file.save(file_path)
                except Exception as e:
                    logging.error(f'File save failed: {str(e)}')
                    return jsonify({
                        'code': 500,
                        'msg': f'File save failed: {str(e)}',
                        'data': None
                    })
            
            # 返回完整的访问URL
            file_url = f"https://[nas.cuagman.fun]:5000/uploads/{new_filename}"
            
            return jsonify({
                'code': 200,
                'msg': 'Upload successful',
                'data': {
                    'filename': new_filename,
                    'url': file_url,
                    'upload_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'size': os.path.getsize(file_path),
                    'compressed': file_length > app.config['COMPRESS_THRESHOLD']
                }
            })
        else:
            return jsonify({
                'code': 400,
                'msg': 'Unsupported file type',
                'data': None
            })
    except Exception as e:
        logging.error(f'Upload failed: {str(e)}')
        return jsonify({
            'code': 500,
            'msg': f'Upload failed: {str(e)}',
            'data': None
        })

@app.route('/wxapp/print', methods=['POST'])
def wxapp_print():
    """处理打印请求"""
    try:
        data = request.json
        if not data or 'file_url' not in data:
            return jsonify({
                'code': 400,
                'msg': 'Invalid request: file_url is required',
                'data': None
            })

        file_url = data['file_url']
        # 在这里添加打印逻辑（例如，发送到打印机）
        print(f"Printing file: {file_url}")

        return jsonify({
            'code': 200,
            'msg': 'Print request received',
            'data': {
                'file_url': file_url,
                'status': 'queued'
            }
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'Print failed: {str(e)}',
            'data': None
        })

if __name__ == '__main__':
    # 启用详细日志
    logging.basicConfig(level=logging.DEBUG)
    # 确保证书路径正确
    ssl_context = ('/path/to/fullchain.pem', '/path/to/privkey.pem')
    app.run(host='::', port=5000, ssl_context=ssl_context, debug=False)