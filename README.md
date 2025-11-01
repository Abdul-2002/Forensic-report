# Forensic Report API

An API for generating forensic reports using AI, specifically Google's Gemini models.

## Features

- Case management for forensic investigations
- Document processing (PDFs, images)
- AI-powered report generation using Google's Gemini
- Azure Blob Storage integration for file storage
- MongoDB for data persistence
- RESTful API with FastAPI

## Project Structure

```
forensic-report-api/
├── .env.example
├── .gitignore
├── Dockerfile
├── pyproject.toml
├── README.md
├── requirements.txt
├── models/
│   ├── text_classifier/
│   └── image_segmenter/
├── notebooks/
├── scripts/
├── src/
│   ├── api/
│   │   ├── dependencies.py
│   │   ├── endpoints/
│   │   └── schemas/
│   ├── core/
│   │   ├── config.py
│   │   ├── logging_config.py
│   │   └── security.py
│   ├── db/
│   │   ├── models/
│   │   ├── repositories/
│   │   └── session.py
│   ├── inference/
│   │   ├── exceptions.py
│   │   ├── loader.py
│   │   ├── models/
│   │   ├── pipeline.py
│   │   ├── postprocessing.py
│   │   ├── preprocessing.py
│   │   └── service.py
│   ├── services/
│   ├── utils/
│   │   ├── file_helpers.py
│   │   └── audit_helpers.py
│   ├── monitoring/
│   │   ├── metrics.py
│   │   ├── logging_middleware.py
│   │   └── health_checks.py
│   ├── admin/
│   │   ├── admin_routes.py
│   │   └── dashboard_service.py
│   └── main.py
├── tests/
│   ├── conftest.py
│   ├── integration/
│   └── unit/
├── nginx/
└── .github/
    └── workflows/
```

## Getting Started

### Prerequisites

- Docker
- Python 3.10 or higher (for local development)
- MongoDB (running separately)
- Azure Blob Storage account
- Google API key for Gemini models
- OpenAI API key (optional, for embeddings)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/forensic-report-api.git
   cd forensic-report-api
   ```

2. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

3. Update the `.env` file with your credentials:
   - MongoDB connection string (pointing to your MongoDB instance)
   - Azure Blob Storage connection string
   - Google API key
   - OpenAI API key (if using embeddings)

4. Create necessary directories:
   ```bash
   mkdir -p uploads/reports uploads/images uploads/exhibits
   ```

5. Build the Docker image:
   ```bash
   docker build -t forensic-report-api .
   ```

6. Run the container:
   ```bash
   docker run -d --name forensic-api \
     -p 8000:8000 \
     -v $(pwd)/uploads:/app/uploads \
     --env-file .env \
     forensic-report-api
   ```

   On Windows PowerShell, use:
   ```powershell
   docker run -d --name forensic-api `
     -p 8000:8000 `
     -v ${PWD}/uploads:/app/uploads `
     --env-file .env `
     forensic-report-api
   ```

7. The API will be available at http://localhost:8000

### API Documentation

Once the API is running, you can access the documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

### Running Tests

```bash
# Run tests inside the container
docker exec forensic-api pytest

# Or run tests locally
python -m pytest
```

### Code Formatting

```bash
# Format code inside the container
docker exec forensic-api black .
docker exec forensic-api isort .

# Or format code locally
black .
isort .
```

### Stopping and Cleaning Up

```bash
# Stop the container
docker stop forensic-api

# Remove the container
docker rm forensic-api

# Remove the image if needed
docker rmi forensic-report-api
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
