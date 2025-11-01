import os
import json
import shutil
from dotenv import load_dotenv
from utils.Mongodbcnnection import MongoDBConnection  # Import your MongoDB connection class
from azure.storage.blob import BlobServiceClient
import tempfile
import google.generativeai as genai
from src.core.config import GOOGLE_API_KEY, GEMINI_MODEL
from src.core.logging_config import get_logger

# Load environment variables
load_dotenv()

# Set up logging
logger = get_logger(__name__)

# Load system prompts from JSON file
SYSTEM_PROMPTS_FILE = "src/controller/system_prompts.json"  # Assumes file is in the same directory

def load_system_prompts() -> dict:
    """
    Load system prompts from a JSON file.
    Returns a dictionary mapping sections to their prompts.
    """
    try:
        with open(SYSTEM_PROMPTS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"System prompts file '{SYSTEM_PROMPTS_FILE}' not found.")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in '{SYSTEM_PROMPTS_FILE}'.")

class CaseQueryProcessor:
    def __init__(self, case_id: str, section: str):
        """
        Initialize the query processor with the case ID and section.

        :param case_id: The ID of the case to process.
        :param section: The specific section to use for querying (e.g., "Background Information").
        """
        self.case_id = case_id
        self.section = section
        self.mongo_connection = MongoDBConnection()  # Use your MongoDBConnection class
        self.db = self.mongo_connection.get_database()
        self.collection = self.db["case_add"]  # Hardcoded to match COLLECTION_NAME from case_router.py
        self.system_prompts = load_system_prompts()
        self.temp_dir = None  # Temporary directory for downloaded documents

        # Configure Gemini API
        self.api_key = GOOGLE_API_KEY
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not set in environment variables")
        genai.configure(api_key=self.api_key)

        # Initialize Gemini model
        self.model = genai.GenerativeModel(GEMINI_MODEL)

        # Azure Blob Storage configuration
        self.connection_string = os.getenv("AZURE_CONNECTION_STRING")
        if not self.connection_string:
            raise ValueError("AZURE_CONNECTION_STRING not set in environment variables")
        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        self.container_name = "original-data"  # Matches case_router.py and CRUD_utils.py

    def download_case_documents(self) -> str:
        """
        Download all document files related to the case from Azure Blob Storage.
        """
        # Get the absolute path of the project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Define temp_files directory at the root level
        self.temp_dir = os.path.join(project_root, "temp_files", self.case_id)

        # Ensure the directory exists
        os.makedirs(self.temp_dir, exist_ok=True)

        # Case-specific document folder in Azure Storage
        case_id_folder = f"{self.case_id}/reports/"

        # List blobs in the case-specific documents folder
        container_client = self.blob_service_client.get_container_client(self.container_name)
        blobs = list(container_client.list_blobs(name_starts_with=case_id_folder))

        if not blobs:
            logger.warning(f"No documents found for case ID: {self.case_id} in {case_id_folder}")
            return self.temp_dir

        logger.info(f"Downloading {len(blobs)} files for case {self.case_id} from {case_id_folder}")

        # Download each document file
        for blob in blobs:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob.name)
            file_path = os.path.join(self.temp_dir, os.path.basename(blob.name))

            with open(file_path, "wb") as f:
                blob_data = blob_client.download_blob()
                f.write(blob_data.readall())

            logger.info(f"Downloaded: {blob.name} -> {file_path}")

        return self.temp_dir

    def query(self, user_query: str = "Provide me whatever information you can provide me in the format for which I have provided") -> str:
        """
        Process the user's query using Gemini model.
        """
        try:
            # Download case documents
            docs_dir = self.download_case_documents()

            # Process documents to extract text
            from src.inference.preprocessing import process_pdf_for_gemini, process_docx, process_txt

            # Get list of files
            import glob
            pdf_files = glob.glob(os.path.join(docs_dir, "*.pdf"))
            docx_files = glob.glob(os.path.join(docs_dir, "*.docx"))
            txt_files = glob.glob(os.path.join(docs_dir, "*.txt"))

            all_content = []

            # Process each file type
            for pdf_file in pdf_files:
                content = process_pdf_for_gemini(pdf_file)
                if content:
                    all_content.append(content)

            for docx_file in docx_files:
                content = process_docx(docx_file)
                if content:
                    all_content.append(content)

            for txt_file in txt_files:
                content = process_txt(txt_file)
                if content:
                    all_content.append(content)

            if not all_content:
                return "No document content found for analysis."

            # Combine all content
            document_text = "\n\n".join(all_content)

            # Retrieve the appropriate system prompt for the section
            system_prompt = self.system_prompts.get(self.section, "Default system prompt: Answer based on the provided documents.")

            # Construct prompt for Gemini
            prompt = f"""
            {system_prompt}

            The following are the case documents:
            {document_text[:30000]}  # Limit text to avoid token limits

            User query: {user_query}
            """

            # Generate response with Gemini
            response = self.model.generate_content(prompt)

            if hasattr(response, "text"):
                return response.text
            else:
                return "Error: Unable to generate response from Gemini model."

        except Exception as e:
            logger.error(f"Error in query processing: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Error processing query: {str(e)}"

    def __del__(self):
        """
        Clean up temporary directory.
        """
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)  # Remove temporary directory