Framework Integrations
======================

This guide provides comprehensive integration examples for popular Python web frameworks, serverless platforms, and deployment scenarios. Each section includes production-ready code examples and best practices.

.. contents::
   :local:
   :depth: 2

Django Integration
------------------

View-Based Conversion
~~~~~~~~~~~~~~~~~~~~~

Basic file upload and conversion view:

.. code-block:: python

   # views.py
   from django.http import HttpResponse, JsonResponse
   from django.views.decorators.http import require_http_methods
   from django.views.decorators.csrf import csrf_exempt
   from all2md import to_markdown
   from all2md.options import PdfOptions, HtmlOptions
   from all2md.exceptions import All2MdError
   import logging

   logger = logging.getLogger(__name__)

   @csrf_exempt  # Use proper CSRF in production
   @require_http_methods(["POST"])
   def convert_document(request):
       """Convert uploaded document to Markdown."""
       if 'document' not in request.FILES:
           return JsonResponse({'error': 'No file provided'}, status=400)

       uploaded_file = request.FILES['document']
       file_ext = uploaded_file.name.lower().split('.')[-1]

       # Validate file size (10MB limit)
       max_size = 10 * 1024 * 1024
       if uploaded_file.size > max_size:
           return JsonResponse({
               'error': f'File too large. Max size: {max_size} bytes'
           }, status=400)

       try:
           # Configure security options based on file type
           if file_ext == 'pdf':
               options = PdfOptions(
                   attachment_mode='skip',
                   pages=[1, 2, 3, 4, 5]  # Limit to first 5 pages
               )
           elif file_ext in ['html', 'htm']:
               options = HtmlOptions(
                   strip_dangerous_elements=True,
                   attachment_mode='skip',
                   network=None  # Use env var ALL2MD_DISABLE_NETWORK
               )
           else:
               options = None

           # Convert document
           markdown = to_markdown(
               uploaded_file.temporary_file_path(),
               parser_options=options
           )

           # Return markdown
           return HttpResponse(markdown, content_type='text/markdown')

       except All2MdError as e:
           logger.error(f"Conversion failed: {e}")
           return JsonResponse({'error': str(e)}, status=500)

   # urls.py
   from django.urls import path
   from . import views

   urlpatterns = [
       path('api/convert/', views.convert_document, name='convert_document'),
   ]

Class-Based Views
~~~~~~~~~~~~~~~~~

Using Django's class-based views:

.. code-block:: python

   # views.py
   from django.views import View
   from django.http import HttpResponse, JsonResponse
   from django.utils.decorators import method_decorator
   from django.views.decorators.csrf import csrf_exempt
   from all2md import to_markdown
   import tempfile
   from pathlib import Path

   @method_decorator(csrf_exempt, name='dispatch')
   class DocumentConversionView(View):
       """Handle document conversion requests."""

       ALLOWED_FORMATS = ['pdf', 'docx', 'pptx', 'html', 'txt']
       MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

       def post(self, request):
           """Handle POST request with file upload."""
           # Validate request
           if 'file' not in request.FILES:
               return JsonResponse({'error': 'No file provided'}, status=400)

           uploaded_file = request.FILES['file']

           # Validate file type
           file_ext = Path(uploaded_file.name).suffix.lower().lstrip('.')
           if file_ext not in self.ALLOWED_FORMATS:
               return JsonResponse({
                   'error': f'Unsupported format. Allowed: {self.ALLOWED_FORMATS}'
               }, status=400)

           # Validate file size
           if uploaded_file.size > self.MAX_FILE_SIZE:
               return JsonResponse({
                   'error': f'File too large. Max: {self.MAX_FILE_SIZE} bytes'
               }, status=413)

           # Convert document
           try:
               markdown = self._convert_file(uploaded_file, file_ext)
               return HttpResponse(
                   markdown,
                   content_type='text/markdown',
                   headers={'Content-Disposition': f'attachment; filename="{uploaded_file.name}.md"'}
               )
           except Exception as e:
               return JsonResponse({'error': str(e)}, status=500)

       def _convert_file(self, uploaded_file, file_ext: str) -> str:
           """Convert uploaded file to markdown."""
           # Write to temporary file
           with tempfile.NamedTemporaryFile(suffix=f'.{file_ext}', delete=False) as tmp:
               for chunk in uploaded_file.chunks():
                   tmp.write(chunk)
               tmp_path = tmp.name

           try:
               markdown = to_markdown(tmp_path, attachment_mode='skip')
               return markdown
           finally:
               # Clean up temp file
               Path(tmp_path).unlink(missing_ok=True)

Django Admin Integration
~~~~~~~~~~~~~~~~~~~~~~~~~

Add document conversion to Django admin:

.. code-block:: python

   # models.py
   from django.db import models

   class Document(models.Model):
       """Document model with conversion support."""
       title = models.CharField(max_length=200)
       file = models.FileField(upload_to='documents/')
       markdown_content = models.TextField(blank=True)
       converted_at = models.DateTimeField(null=True, blank=True)
       created_at = models.DateTimeField(auto_now_add=True)

       def convert_to_markdown(self):
           """Convert document file to markdown."""
           from all2md import to_markdown
           from django.utils import timezone

           self.markdown_content = to_markdown(
               self.file.path,
               attachment_mode='skip'
           )
           self.converted_at = timezone.now()
           self.save()

   # admin.py
   from django.contrib import admin
   from django.utils.html import format_html
   from .models import Document

   @admin.register(Document)
   class DocumentAdmin(admin.ModelAdmin):
       list_display = ['title', 'created_at', 'converted_at', 'convert_action']
       readonly_fields = ['markdown_content', 'converted_at']

       def convert_action(self, obj):
           """Display convert button."""
           if obj.pk:
               return format_html(
                   '<a class="button" href="/admin/convert-doc/{}/"> Convert</a>',
                   obj.pk
               )
           return '-'

       convert_action.short_description = 'Convert'

       def get_urls(self):
           from django.urls import path
           urls = super().get_urls()
           custom_urls = [
               path('convert-doc/<int:doc_id>/',
                    self.admin_site.admin_view(self.convert_document),
                    name='convert-document'),
           ]
           return custom_urls + urls

       def convert_document(self, request, doc_id):
           from django.shortcuts import redirect
           from django.contrib import messages

           doc = Document.objects.get(pk=doc_id)
           try:
               doc.convert_to_markdown()
               messages.success(request, f'Document "{doc.title}" converted successfully')
           except Exception as e:
               messages.error(request, f'Conversion failed: {e}')

           return redirect('admin:myapp_document_change', doc_id)

Background Task with Celery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Process documents asynchronously:

.. code-block:: python

   # tasks.py
   from celery import shared_task
   from .models import Document
   from all2md import to_markdown
   from all2md.exceptions import All2MdError
   import logging

   logger = logging.getLogger(__name__)

   @shared_task(bind=True, max_retries=3)
   def convert_document_task(self, document_id: int):
       """Convert document to markdown asynchronously."""
       try:
           document = Document.objects.get(pk=document_id)

           # Convert document
           markdown = to_markdown(
               document.file.path,
               attachment_mode='skip'
           )

           # Save result
           document.markdown_content = markdown
           from django.utils import timezone
           document.converted_at = timezone.now()
           document.save()

           logger.info(f"Converted document {document_id}")
           return f"Success: {document.title}"

       except Document.DoesNotExist:
           logger.error(f"Document {document_id} not found")
           return f"Error: Document not found"

       except All2MdError as e:
           logger.error(f"Conversion failed for document {document_id}: {e}")
           # Retry with exponential backoff
           raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

   # views.py - Trigger background task
   from .tasks import convert_document_task

   def upload_document(request):
       """Upload document and trigger conversion."""
       if request.method == 'POST':
           document = Document.objects.create(
               title=request.POST['title'],
               file=request.FILES['file']
           )
           # Trigger async conversion
           convert_document_task.delay(document.id)

           return JsonResponse({
               'message': 'Document uploaded, conversion started',
               'document_id': document.id
           })

FastAPI Integration
-------------------

Basic File Upload
~~~~~~~~~~~~~~~~~

Simple FastAPI endpoint for document conversion:

.. code-block:: python

   # main.py
   from fastapi import FastAPI, UploadFile, File, HTTPException
   from fastapi.responses import PlainTextResponse
   from all2md import to_markdown
   from all2md.exceptions import All2MdError
   import tempfile
   from pathlib import Path

   app = FastAPI(title="Document Converter API")

   @app.post("/convert", response_class=PlainTextResponse)
   async def convert_document(
       file: UploadFile = File(...),
       max_pages: int = 10
   ):
       """Convert uploaded document to Markdown.

       Args:
           file: Document file to convert
           max_pages: Maximum pages to process (PDF only)

       Returns:
           Markdown content as plain text
       """
       # Validate file type
       allowed_types = {
           'application/pdf': 'pdf',
           'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
           'text/html': 'html'
       }

       if file.content_type not in allowed_types:
           raise HTTPException(
               status_code=400,
               detail=f"Unsupported file type: {file.content_type}"
           )

       # Save to temporary file
       suffix = f".{allowed_types[file.content_type]}"
       with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
           content = await file.read()
           tmp.write(content)
           tmp_path = tmp.name

       try:
           # Convert document
           markdown = to_markdown(
               tmp_path,
               pages=list(range(1, max_pages + 1)) if suffix == '.pdf' else None,
               attachment_mode='skip'
           )
           return markdown

       except All2MdError as e:
           raise HTTPException(status_code=500, detail=str(e))

       finally:
           # Cleanup
           Path(tmp_path).unlink(missing_ok=True)

Async with Background Tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use FastAPI's background tasks for processing:

.. code-block:: python

   from fastapi import FastAPI, UploadFile, BackgroundTasks
   from fastapi.responses import JSONResponse
   from pydantic import BaseModel
   from all2md import to_markdown
   import uuid
   from pathlib import Path
   from typing import Dict

   app = FastAPI()

   # In-memory storage (use Redis/database in production)
   conversion_status: Dict[str, dict] = {}

   class ConversionResponse(BaseModel):
       job_id: str
       status: str
       message: str

   class ConversionResult(BaseModel):
       job_id: str
       status: str
       markdown: str | None = None
       error: str | None = None

   def process_document(job_id: str, file_path: str):
       """Background task to process document."""
       try:
           markdown = to_markdown(file_path, attachment_mode='skip')
           conversion_status[job_id] = {
               'status': 'completed',
               'markdown': markdown
           }
       except Exception as e:
           conversion_status[job_id] = {
               'status': 'failed',
               'error': str(e)
           }
       finally:
           # Cleanup temp file
           Path(file_path).unlink(missing_ok=True)

   @app.post("/convert/async", response_model=ConversionResponse)
   async def convert_async(
       file: UploadFile,
       background_tasks: BackgroundTasks
   ):
       """Start async document conversion."""
       # Generate job ID
       job_id = str(uuid.uuid4())

       # Save uploaded file
       upload_dir = Path("/tmp/uploads")
       upload_dir.mkdir(exist_ok=True)
       file_path = upload_dir / f"{job_id}_{file.filename}"

       with open(file_path, 'wb') as f:
           content = await file.read()
           f.write(content)

       # Mark as processing
       conversion_status[job_id] = {'status': 'processing'}

       # Add background task
       background_tasks.add_task(process_document, job_id, str(file_path))

       return ConversionResponse(
           job_id=job_id,
           status='processing',
           message='Conversion started'
       )

   @app.get("/convert/status/{job_id}", response_model=ConversionResult)
   async def get_conversion_status(job_id: str):
       """Get conversion status and result."""
       if job_id not in conversion_status:
           raise HTTPException(status_code=404, detail="Job not found")

       status_data = conversion_status[job_id]
       return ConversionResult(
           job_id=job_id,
           status=status_data['status'],
           markdown=status_data.get('markdown'),
           error=status_data.get('error')
       )

Streaming Response
~~~~~~~~~~~~~~~~~~

Stream large document conversions:

.. code-block:: python

   from fastapi import FastAPI
   from fastapi.responses import StreamingResponse
   from all2md import to_markdown
   from all2md.options import PdfOptions
   import io

   app = FastAPI()

   @app.get("/convert/stream/{filename}")
   async def stream_conversion(filename: str):
       """Stream document conversion in chunks."""

       def generate_chunks():
           """Generate markdown in chunks."""
           # Process document in page chunks
           total_pages = 100  # Get from metadata
           chunk_size = 10

           for start in range(1, total_pages + 1, chunk_size):
               end = min(start + chunk_size - 1, total_pages)
               pages = list(range(start, end + 1))

               options = PdfOptions(
                   pages=pages,
                   attachment_mode='skip'
               )

               chunk_markdown = to_markdown(filename, parser_options=options)
               yield chunk_markdown.encode('utf-8')

       return StreamingResponse(
           generate_chunks(),
           media_type='text/markdown',
           headers={'Content-Disposition': f'attachment; filename="{filename}.md"'}
       )

Flask Integration
-----------------

Basic Flask App
~~~~~~~~~~~~~~~

Simple Flask application with document conversion:

.. code-block:: python

   # app.py
   from flask import Flask, request, Response, jsonify
   from werkzeug.utils import secure_filename
   from all2md import to_markdown
   from all2md.exceptions import All2MdError
   import tempfile
   from pathlib import Path

   app = Flask(__name__)
   app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB limit

   ALLOWED_EXTENSIONS = {'pdf', 'docx', 'pptx', 'html', 'txt'}

   def allowed_file(filename):
       return '.' in filename and \
              filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

   @app.route('/convert', methods=['POST'])
   def convert():
       """Convert uploaded document to Markdown."""
       if 'file' not in request.files:
           return jsonify({'error': 'No file provided'}), 400

       file = request.files['file']

       if file.filename == '':
           return jsonify({'error': 'No file selected'}), 400

       if not allowed_file(file.filename):
           return jsonify({'error': 'File type not allowed'}), 400

       try:
           # Convert document
           markdown = to_markdown(file, attachment_mode='skip')

           return Response(
               markdown,
               mimetype='text/markdown',
               headers={'Content-Disposition': f'attachment; filename="{filename}.md"'}
           )

       except All2MdError as e:
           return jsonify({'error': str(e)}), 500

       finally:
           Path(tmp_path).unlink(missing_ok=True)

   if __name__ == '__main__':
       app.run(debug=True)

Flask Blueprint
~~~~~~~~~~~~~~~

Organize as a Flask blueprint:

.. code-block:: python

   # converter/blueprint.py
   from flask import Blueprint, request, jsonify, send_file
   from all2md import to_markdown
   from pathlib import Path
   import tempfile

   converter_bp = Blueprint('converter', __name__, url_prefix='/api/converter')

   @converter_bp.route('/convert', methods=['POST'])
   def convert_document():
       """Convert document endpoint."""
       file = request.files.get('file')
       if not file:
           return jsonify({'error': 'No file provided'}), 400

       # Process file
       with tempfile.NamedTemporaryFile(suffix=Path(file.filename).suffix) as tmp:
           file.save(tmp.name)
           markdown = to_markdown(tmp.name, attachment_mode='skip')

       return jsonify({'markdown': markdown})

   @converter_bp.route('/formats', methods=['GET'])
   def supported_formats():
       """List supported formats."""
       from all2md.constants import SUPPORTED_FORMATS
       return jsonify({'formats': list(SUPPORTED_FORMATS.keys())})

   # app.py
   from flask import Flask
   from converter.blueprint import converter_bp

   app = Flask(__name__)
   app.register_blueprint(converter_bp)

Error Handling
~~~~~~~~~~~~~~

Comprehensive error handling:

.. code-block:: python

   from flask import Flask, jsonify
   from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
   from all2md.exceptions import All2MdError
   import logging

   app = Flask(__name__)
   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)

   @app.errorhandler(RequestEntityTooLarge)
   def handle_file_too_large(e):
       """Handle file size limit exceeded."""
       logger.warning(f"File too large: {e}")
       return jsonify({
           'error': 'File too large',
           'max_size': app.config['MAX_CONTENT_LENGTH']
       }), 413

   @app.errorhandler(All2MdError)
   def handle_conversion_error(e):
       """Handle all2md conversion errors."""
       logger.error(f"Conversion error: {e}")
       return jsonify({'error': f'Conversion failed: {str(e)}'}), 500

   @app.errorhandler(Exception)
   def handle_unexpected_error(e):
       """Handle unexpected errors."""
       logger.error(f"Unexpected error: {e}", exc_info=True)
       return jsonify({'error': 'Internal server error'}), 500

AWS Lambda
----------

Basic Lambda Function
~~~~~~~~~~~~~~~~~~~~~

Deploy all2md as AWS Lambda function:

.. code-block:: python

   # lambda_function.py
   import json
   import base64
   import tempfile
   from pathlib import Path
   from all2md import to_markdown
   from all2md.options import PdfOptions

   def lambda_handler(event, context):
       """AWS Lambda handler for document conversion.

       Event format:
       {
           "file_content": "base64-encoded file content",
           "filename": "document.pdf",
           "options": {
               "max_pages": 10,
               "attachment_mode": "skip"
           }
       }
       """
       try:
           # Extract parameters
           file_content_b64 = event.get('file_content')
           filename = event.get('filename', 'document.pdf')
           options_dict = event.get('options', {})

           if not file_content_b64:
               return {
                   'statusCode': 400,
                   'body': json.dumps({'error': 'No file_content provided'})
               }

           # Decode file content
           file_content = base64.b64decode(file_content_b64)

           # Write to /tmp (Lambda's writable directory)
           tmp_path = Path('/tmp') / filename
           tmp_path.write_bytes(file_content)

           # Prepare conversion options
           max_pages = options_dict.get('max_pages', 50)
           options = PdfOptions(
               pages=list(range(1, max_pages + 1)),
               attachment_mode=options_dict.get('attachment_mode', 'skip')
           )

           # Convert document
           markdown = to_markdown(str(tmp_path), parser_options=options)

           # Cleanup
           tmp_path.unlink()

           return {
               'statusCode': 200,
               'headers': {'Content-Type': 'text/markdown'},
               'body': markdown
           }

       except Exception as e:
           return {
               'statusCode': 500,
               'body': json.dumps({'error': str(e)})
           }

Lambda Deployment Package
~~~~~~~~~~~~~~~~~~~~~~~~~

Create deployment package with dependencies:

.. code-block:: bash

   # Create deployment package
   mkdir lambda-package
   cd lambda-package

   # Install all2md and dependencies
   pip install 'all2md[pdf,docx]' -t .

   # Add your lambda function
   cp ../lambda_function.py .

   # Create zip
   zip -r lambda-deployment.zip .

Lambda with S3 Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Process documents from S3:

.. code-block:: python

   import boto3
   import json
   from all2md import to_markdown
   from pathlib import Path

   s3_client = boto3.client('s3')

   def lambda_handler(event, context):
       """Process S3 upload and convert to markdown."""
       # Get S3 object info from event
       for record in event['Records']:
           bucket = record['s3']['bucket']['name']
           key = record['s3']['object']['key']

           # Download file from S3
           download_path = f'/tmp/{Path(key).name}'
           s3_client.download_file(bucket, key, download_path)

           try:
               # Convert to markdown
               markdown = to_markdown(download_path, attachment_mode='skip')

               # Upload markdown back to S3
               output_key = f"{Path(key).stem}.md"
               s3_client.put_object(
                   Bucket=bucket,
                   Key=f"converted/{output_key}",
                   Body=markdown.encode('utf-8'),
                   ContentType='text/markdown'
               )

               return {
                   'statusCode': 200,
                   'body': json.dumps({
                       'input': key,
                       'output': f"converted/{output_key}"
                   })
               }

           finally:
               Path(download_path).unlink(missing_ok=True)

Docker Deployment
-----------------

Basic Dockerfile
~~~~~~~~~~~~~~~~

Containerize all2md application:

.. code-block:: dockerfile

   # Dockerfile
   FROM python:3.12-slim

   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       gcc \
       && rm -rf /var/lib/apt/lists/*

   # Set working directory
   WORKDIR /app

   # Install Python dependencies
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   # Copy application code
   COPY . .

   # Create upload directory
   RUN mkdir -p /app/uploads /app/output

   # Expose port
   EXPOSE 8000

   # Run application
   CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

.. code-block:: text

   # requirements.txt
   all2md[all]==0.1.0
   fastapi==0.109.0
   uvicorn[standard]==0.27.0
   python-multipart==0.0.6

Docker Compose
~~~~~~~~~~~~~~

Multi-container setup with Redis queue:

.. code-block:: yaml

   # docker-compose.yml
   version: '3.8'

   services:
     web:
       build: .
       ports:
         - "8000:8000"
       environment:
         - ALL2MD_DISABLE_NETWORK=true
         - REDIS_URL=redis://redis:6379
       volumes:
         - ./uploads:/app/uploads
         - ./output:/app/output
       depends_on:
         - redis
         - worker

     worker:
       build: .
       command: celery -A tasks worker --loglevel=info
       environment:
         - ALL2MD_DISABLE_NETWORK=true
         - REDIS_URL=redis://redis:6379
       volumes:
         - ./uploads:/app/uploads
         - ./output:/app/output
       depends_on:
         - redis

     redis:
       image: redis:7-alpine
       ports:
         - "6379:6379"

Production Best Practices
--------------------------

Security Configuration
~~~~~~~~~~~~~~~~~~~~~~

Production-ready security settings:

.. code-block:: python

   # config.py
   import os
   from all2md.options import HtmlOptions, PdfOptions
   from all2md.options.common import NetworkFetchOptions, LocalFileAccessOptions

   class ProductionConfig:
       """Production configuration for all2md."""

       # File limits
       MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
       MAX_PAGES = 50

       # Security settings
       HTML_OPTIONS = HtmlOptions(
           strip_dangerous_elements=True,
           attachment_mode='skip',
           network=NetworkFetchOptions(
               allow_remote_fetch=False  # Block SSRF
           ),
           local_files=LocalFileAccessOptions(
               allow_local_files=False  # Block local file access
           )
       )

       PDF_OPTIONS = PdfOptions(
           attachment_mode='skip',
           pages=list(range(1, MAX_PAGES + 1))
       )

       # Environment variables
       @staticmethod
       def configure_environment():
           """Set security environment variables."""
           os.environ['ALL2MD_DISABLE_NETWORK'] = '1'
           os.environ['ALL2MD_ATTACHMENT_MODE'] = 'skip'

Rate Limiting
~~~~~~~~~~~~~

Implement rate limiting (Flask example):

.. code-block:: python

   from flask import Flask
   from flask_limiter import Limiter
   from flask_limiter.util import get_remote_address

   app = Flask(__name__)
   limiter = Limiter(
       app=app,
       key_func=get_remote_address,
       default_limits=["100 per hour"]
   )

   @app.route('/convert', methods=['POST'])
   @limiter.limit("10 per minute")  # Stricter limit for conversion
   def convert():
       # ... conversion logic ...
       pass

Health Checks
~~~~~~~~~~~~~

Implement health check endpoints:

.. code-block:: python

   from fastapi import FastAPI
   from all2md import to_markdown
   import tempfile

   app = FastAPI()

   @app.get("/health")
   async def health_check():
       """Basic health check."""
       return {"status": "ok"}

   @app.get("/health/ready")
   async def readiness_check():
       """Readiness check with conversion test."""
       try:
           # Test conversion
           with tempfile.NamedTemporaryFile(suffix='.txt', mode='w') as tmp:
               tmp.write("# Test")
               tmp.flush()
               markdown = to_markdown(tmp.name)

           return {"status": "ready"}
       except Exception as e:
           return {"status": "not_ready", "error": str(e)}, 503

See Also
--------

* :doc:`security` - Security best practices
* :doc:`performance` - Performance optimization
* :doc:`mcp` - MCP server integration
* :doc:`cli` - Command-line interface
