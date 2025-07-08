import os
import tempfile
import shutil
from flask import Flask, request, send_file, render_template, Response
from document_parser import DocumentModel
from ppt_generator import PPTGenerator

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_ppt():
    # 检查是否有文件上传
    if 'document' not in request.files:
        return Response("未上传文件", status=400)
    
    file = request.files['document']
    
    # 检查文件是否有名称
    if file.filename == '':
        return Response("未选择文件", status=400)
    
    # 检查文件类型
    if not file.filename.endswith(('.txt', '.md')):
        return Response("不支持的文件类型，仅支持.txt和.md文件", status=400)
    
    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    input_file_path = os.path.join(temp_dir, file.filename)
    output_file_path = os.path.join(temp_dir, 'output.pptx')
    
    try:
        # 保存上传的文件
        file.save(input_file_path)
        
        # 解析文档
        doc_model = DocumentModel(input_file_path)
        doc_model.parse()
        
        # 下载图片
        doc_model.download_images(temp_dir)
        
        # 生成PPT
        ppt_generator = PPTGenerator()
        ppt_generator.generate(doc_model, output_file_path)
        
        # 返回生成的PPT文件
        return send_file(
            output_file_path,
            as_attachment=True,
            attachment_filename='generated-presentation.pptx',
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation'
        )
    except Exception as e:
        print(f"Error generating PPT: {str(e)}")
        return Response(f"生成PPT时出错: {str(e)}", status=500)
    finally:
        # 清理临时文件
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error cleaning up temp files: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True)    