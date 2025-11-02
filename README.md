# Forensic Report API

A comprehensive REST API for generating forensic reports using AI, specifically Google's Gemini models. This API provides case management, document processing, and AI-powered report generation capabilities for forensic investigations.

## Features

- **Case Management**: Create, update, and manage forensic investigation cases
- **Document Processing**: Upload and process PDFs, images, and documents (DOCX, TXT)
- **AI-Powered Report Generation**: Generate forensic reports using Google's Gemini AI models
- **Azure Blob Storage Integration**: Secure cloud storage for documents and generated reports
- **MongoDB Persistence**: Robust data storage for cases, users, and reports
- **WebSocket Support**: Real-time communication via Socket.IO for long-running operations
- **RESTful API**: FastAPI-based API with automatic OpenAPI documentation
- **User Authentication**: User management and authentication system
- **System Prompts Management**: Dynamic system prompt management for different case types
- **Health Monitoring**: Health checks and metrics endpoint for monitoring
- **File Upload/Download**: Support for file uploads and secure download links via SAS tokens

## Project Structure

```
forensic-report-api/
├── main.py                    # Entry point (compatibility wrapper for src/main.py)
├── Dockerfile                  # Docker configuration
├── Dockerfile.minimal         # Minimal Docker configuration
├── requirements.txt           # Python dependencies
├── pyproject.toml             # Project metadata and tooling config
├── bitbucket-pipelines.yml   # CI/CD pipeline configuration
├── nginx/                     # Nginx configuration
│   └── nginx.conf
├── src/                       # Main application source code
│   ├── main.py               # FastAPI application entry point
│   ├── api/                  # API endpoints and schemas
│   │   ├── endpoints/        # Individual endpoint modules
│   │   │   ├── admin.py
│   │   │   ├── cases.py
│   │   │   ├── case_add.py
│   │   │   ├── health.py
│   │   │   ├── login.py
│   │   │   ├── predictions.py
│   │   │   ├── prompts.py
│   │   │   └── reports.py
│   │   ├── schemas/          # Pydantic models for request/response validation
│   │   └── dependencies.py  # Dependency injection utilities
│   ├── admin/                # Admin dashboard functionality
│   │   ├── admin_routes.py
│   │   └── dashboard_service.py
│   ├── controller/           # Business logic controllers
│   │   ├── gemini_case_handler.py
│   │   └── prompting.py
│   ├── core/                 # Core configuration and utilities
│   │   ├── config.py        # Application configuration
│   │   ├── logging_config.py
│   │   ├── openapi.py
│   │   └── security.py
│   ├── db/                   # Database layer
│   │   ├── models/          # Database models
│   │   ├── repositories/    # Repository pattern implementation
│   │   └── session.py       # Database session management
│   ├── inference/           # AI inference pipeline
│   │   ├── models/         # AI model wrappers (Gemini)
│   │   ├── pipeline.py
│   │   ├── preprocessing.py
│   │   ├── postprocessing.py
│   │   ├── service.py
│   │   ├── loader.py
│   │   └── exceptions.py
│   ├── monitoring/          # Monitoring and observability
│   │   ├── health_checks.py
│   │   ├── logging_middleware.py
│   │   └── metrics.py
│   ├── routers/             # Legacy router modules (being phased out)
│   │   ├── case_router.py
│   │   ├── login_router.py
│   │   ├── prompts_router.py
│   │   └── report_routes.py
│   ├── services/           # Service layer
│   ├── socket/             # WebSocket/Socket.IO handlers
│   │   ├── socket_manager.py
│   │   ├── handlers.py
│   │   ├── case_query_handler.py
│   │   └── report_handler.py
│   └── utils/              # Utility functions
│       ├── file_helpers.py
│       ├── audit_helpers.py
│       └── text_parser.py
├── utils/                   # Legacy utilities (to be migrated)
│   ├── Mongodbcnnection.py  # Legacy MongoDB connection (use src/db/session.py instead)
│   └── CRUD_utils.py       # Legacy CRUD utilities (use repositories instead)
├── examples/               # Example scripts
│   └── parse_text_example.py
├── scripts/                # Utility scripts
│   ├── import_prompts.py
│   └── run_batch_inference.py
├── tests/                  # Test suite
│   ├── conftest.py
│   ├── integration/
│   └── unit/
└── system_prompts_backup.json  # Backup of system prompts
```

## Prerequisites

- **Python**: 3.10 or higher
- **MongoDB**: Running instance (local or cloud)
- **Azure Blob Storage**: Account for file storage
- **Google API Key**: For Gemini AI models
- **Docker** (optional, for containerized deployment)

## Installation

### Local Development

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd forensic-report-api
   ```

2. **Create a virtual environment** (using conda as preferred):
   ```bash
   conda create -n forensic-report python=3.11
   conda activate forensic-report
   ```

   Or using venv:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Create a `.env` file** in the root directory:
   ```env
   # MongoDB Configuration
   MONGO_URI=mongodb://localhost:27017
   DATABASE_NAME=forensic_report
   CASE_COLLECTION=case_add
   PROMPTS_COLLECTION=system_prompts

   # Azure Blob Storage
   AZURE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
   AZURE_CONTAINER_NAME=original-data
   ACCOUNT_NAME=your_account_name
   ACCOUNT_KEY=your_account_key

   # Google Gemini AI
   GOOGLE_API_KEY=your_google_api_key
   GEMINI_MODEL=gemini-pro
   GEMINI_IMAGE_MODEL=gemini-pro-vision
   ```

5. **Create necessary directories**:
   ```bash
   mkdir -p uploads/reports uploads/images uploads/exhibits temp_files logs
   ```

6. **Run the application**:
   ```bash
   # Using the main entry point
   python main.py

   # Or directly with uvicorn
   uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
   ```

   The API will be available at `http://localhost:8000`

### Docker Deployment

1. **Build the Docker image**:
   ```bash
   docker build -t forensic-report-api .
   ```

2. **Run the container**:
   ```bash
   docker run -d --name forensic-api \
     -p 8000:8000 \
     -v $(pwd)/uploads:/app/uploads \
     --env-file .env \
     forensic-report-api
   ```

   On Windows PowerShell:
   ```powershell
   docker run -d --name forensic-api `
     -p 8000:8000 `
     -v ${PWD}/uploads:/app/uploads `
     --env-file .env `
     forensic-report-api
   ```

## Environment Variables

### Required Variables

| Variable | Description |
|----------|-------------|
| `MONGO_URI` | MongoDB connection string |
| `DATABASE_NAME` | MongoDB database name |
| `AZURE_CONNECTION_STRING` | Azure Blob Storage connection string |
| `ACCOUNT_NAME` | Azure Storage account name |
| `ACCOUNT_KEY` | Azure Storage account key |
| `GOOGLE_API_KEY` | Google Gemini API key |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CASE_COLLECTION` | MongoDB collection for cases | `case_add` |
| `PROMPTS_COLLECTION` | MongoDB collection for prompts | `system_prompts` |
| `AZURE_CONTAINER_NAME` | Azure container name | `original-data` |
| `GEMINI_MODEL` | Gemini model name | `gemini-pro` |
| `GEMINI_IMAGE_MODEL` | Gemini vision model | `gemini-pro-vision` |

## API Documentation

Once the API is running, you can access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json
- **Health Check**: http://localhost:8000/app/v1/health
- **Metrics**: http://localhost:8000/metrics (Prometheus format)

## Main API Endpoints

### Cases
- `POST /app/v1/cases` - Create a new case
- `GET /app/v1/cases` - List all cases
- `GET /app/v1/cases/{case_id}` - Get case details
- `PUT /app/v1/cases/{case_id}` - Update a case
- `DELETE /app/v1/cases/{case_id}` - Delete a case

### Reports
- `POST /app/v1/reports` - Generate a report
- `GET /app/v1/reports` - List all reports
- `GET /app/v1/reports/{case_id}` - Get reports for a case
- `GET /app/v1/reports/download/{case_id}` - Download report

### Predictions/Inference
- `POST /app/v1/predictions/query` - Query a case using AI

### System Prompts
- `GET /app/v1/prompts` - List all prompts
- `POST /app/v1/prompts` - Create a prompt
- `PUT /app/v1/prompts/{prompt_id}` - Update a prompt
- `DELETE /app/v1/prompts/{prompt_id}` - Delete a prompt
- `POST /app/v1/prompts/import-from-json` - Import prompts from JSON

### Authentication
- `POST /app/v1/login` - User login
- `POST /app/v1/add-user-id` - Create user
- `GET /app/v1/Login-user` - List users

## WebSocket Events

The API supports WebSocket connections via Socket.IO:

- `connect` - Client connection
- `query_case` - Query a case (emits progress updates)
- `generate_report` - Generate a report (emits progress updates)
- `disconnect` - Client disconnection

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/api/test_cases.py
```

### Code Formatting

```bash
# Format code
black .

# Sort imports
isort .

# Type checking
mypy src/
```

### Project Structure Guidelines

- **API Endpoints**: Place in `src/api/endpoints/`
- **Business Logic**: Place in `src/controller/`
- **Database Operations**: Use repositories in `src/db/repositories/`
- **Utility Functions**: Place in `src/utils/`
- **Models/Schemas**: Place in `src/api/schemas/` (for API) or `src/db/models/` (for DB)

## Legacy Code Notes

### Migration Path

The codebase contains some legacy code that should be migrated:

1. **Legacy MongoDB Connection** (`utils/Mongodbcnnection.py`):
   - **Status**: Still in use by some routers
   - **Migration**: Use `src/db/session.py` and `get_db()` instead
   - **Files using legacy**: `src/routers/*.py`, `src/controller/*.py`

2. **Legacy CRUD Utils** (`utils/CRUD_utils.py`):
   - **Status**: Still in use, but `format_object_id` has been deduplicated
   - **Migration**: Use repository pattern from `src/db/repositories/`
   - **Note**: `ReadWrite` class for Azure operations is still needed but should be moved to `src/utils/`

3. **Legacy Routers** (`src/routers/*.py`):
   - **Status**: Functional but should be migrated to use API endpoints pattern
   - **Future**: Consolidate with `src/api/endpoints/`

## Architecture

### Database Layer
- **Session Management**: Singleton pattern via `DatabaseSession`
- **Repository Pattern**: Abstract base repository with specific implementations
- **Models**: Pydantic models for validation and MongoDB documents

### AI Inference Pipeline
1. **Preprocessing**: Extract and prepare documents (PDF, DOCX, TXT)
2. **Inference**: Process with Gemini AI models
3. **Postprocessing**: Extract findings and background sections

### File Storage
- **Local**: Temporary storage during processing
- **Azure Blob**: Permanent storage with SAS token-based access
- **Automatic Cleanup**: Temporary files cleaned after processing

## Monitoring

- **Health Checks**: `/app/v1/health` endpoint
- **Metrics**: Prometheus-compatible metrics at `/metrics`
- **Logging**: Structured logging with configurable levels
- **Error Handling**: Global exception handler with detailed error responses

## Contributing

1. Follow the existing code structure
2. Use type hints for all functions
3. Add docstrings for all public functions/classes
4. Write tests for new features
5. Format code with Black and isort
6. Update this README for significant changes

## Troubleshooting

### MongoDB Connection Issues
- Verify `MONGO_URI` is correct
- Check network connectivity to MongoDB
- Ensure TLS/SSL settings match your MongoDB configuration

### Azure Blob Storage Issues
- Verify connection string format
- Check container exists and is accessible
- Verify account key is correct

### Gemini API Issues
- Verify API key is valid and has quota
- Check rate limits (429 errors)
- Review error logs for specific error messages

## License

This project is licensed under the MIT License - see the LICENSE file for details.
