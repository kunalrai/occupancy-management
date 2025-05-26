from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from datetime import datetime
import os
from dotenv import load_dotenv
from models import db, BadgeAccess
import utils
from werkzeug.utils import secure_filename
from collections import Counter
from sqlalchemy import func
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from io import BytesIO


# Load environment variables
load_dotenv()



app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///badge_access.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'


connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
container_name = os.getenv("AZURE_CONTAINER_NAME")

blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)
# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
db.init_app(app)

@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}

def upload_file_to_blob(file):
    filename = secure_filename(file.filename)
    timestamped_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    blob_client = container_client.get_blob_client(timestamped_filename)

    blob_client.upload_blob(file, overwrite=True)

    return timestamped_filename 

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        if file and utils.allowed_file(file.filename):
            try:
                # Generate unique filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{secure_filename(file.filename)}"
                
                # Read file into memory (BytesIO)
                file_bytes = file.read()
                file_stream = BytesIO(file_bytes)

                # Validate CSV from memory
                validation_result = utils.validate_csv(file_stream)
                if not validation_result['valid']:
                    flash(f"Invalid CSV file: {validation_result['error']}", 'error')
                    return redirect(request.url)
                
                # Rewind file_stream for processing
                file_stream.seek(0)
                utils.process_csv(file_stream, db.session)

                # Upload to Azure Blob Storage
                blob_client = container_client.get_blob_client(filename)
                blob_client.upload_blob(file_bytes, overwrite=True)

                flash('File uploaded and processed successfully!', 'success')
                return redirect(url_for('dashboard'))
            
            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'error')
                return redirect(request.url)

        else:
            flash('Invalid file type. Please upload a CSV file.', 'error')
            return redirect(request.url)

    return render_template('upload.html')

@app.route('/dashboard')
# def dashboard():
#     # Get the latest records
#     records = BadgeAccess.query.order_by(BadgeAccess.initial_login_date.desc()).limit(100).all()
#     return render_template('dashboard.html', records=records)

def dashboard():
    # Get latest 100 records
    records = BadgeAccess.query.order_by(BadgeAccess.initial_login_date.desc()).limit(100).all()

    # Summary Metrics
    total_records = BadgeAccess.query.count()
    unique_sites = db.session.query(BadgeAccess.site_name).distinct().count()
    unique_gid = db.session.query(BadgeAccess.global_id).distinct().count()

    # Date Range
    date_min = db.session.query(func.min(BadgeAccess.initial_login_date)).scalar()
    date_max = db.session.query(func.max(BadgeAccess.initial_login_date)).scalar()
    date_range = f"{date_min.strftime('%Y-%m-%d')} to {date_max.strftime('%Y-%m-%d')}" if date_min and date_max else "N/A"

    # Chart Data
    site_counter = Counter([r.site_name for r in records])
    date_counter = Counter([r.initial_login_date.strftime('%Y-%m-%d') for r in records])

    return render_template('dashboard.html',
        records=records,
        total_records=total_records,
        unique_sites=unique_sites,
        unique_gid=unique_gid,
        date_range=date_range,
        site_labels=list(site_counter.keys()),
        site_counts=list(site_counter.values()),
        date_labels=list(date_counter.keys()),
        date_counts=list(date_counter.values())
    )

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/download-template')
def download_template():
      return send_from_directory(directory=app.config['UPLOAD_FOLDER'], path='template.csv', as_attachment=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)