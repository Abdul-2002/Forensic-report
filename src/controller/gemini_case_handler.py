import os
import io
import json
import glob
import shutil
import tempfile
import logging
from pathlib import Path
from typing import List, Dict, Optional, Union, Any
import time
# Removed unused docx import at the top, added where needed
from dotenv import load_dotenv
import google.generativeai as genai

# Azure imports
from azure.storage.blob import BlobServiceClient

# MongoDB imports
# Make sure this path is correct for your project structure
try:
    from utils.Mongodbcnnection import MongoDBConnection
except ImportError:
    # Fallback or error handling if the path is different in some environments
    logging.error("Could not import MongoDBConnection from utils.Mongodbcnnection. Please check the path.")
    # Provide a clearer error at initialization time
    MongoDBConnection = None

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Moved extract_retry_delay outside the class ---
def extract_retry_delay(error_message: str, default_delay: int = 5) -> int:
    """
    Extract the retry delay from a Gemini API rate limit error message (429).

    Args:
        error_message: The error message string from the Gemini API.
        default_delay: Default delay in seconds to use if extraction fails or not a 429 error.

    Returns:
        The number of seconds to delay before retrying.
    """
    try:
        # Only attempt extraction for 429 errors
        if "429" not in error_message:
            logger.debug("Error is not 429, returning default delay for backoff.")
            return default_delay  # Use default for non-429 errors triggering backoff

        # Look for the retry_delay section in the error message
        if "retry_delay" in error_message:
            # Extract the seconds value using string manipulation
            retry_delay_section = error_message.split("retry_delay {")[1].split("}")[0]
            seconds_str = retry_delay_section.split("seconds:")[1].strip()

            # Convert to integer, handling any trailing characters
            seconds = int(''.join(filter(str.isdigit, seconds_str)))

            # Add a small buffer (e.g., 1-2 seconds or 10%) to the suggested retry time
            # This helps avoid hitting the limit immediately again.
            buffered_delay = seconds + 2  # Add 2 seconds buffer

            logger.info(f"Extracted retry delay from 429 error: {seconds} seconds, using buffered delay: {buffered_delay}s")
            return buffered_delay
        else:
            logger.warning(f"429 error message did not contain 'retry_delay' details. Using default delay: {default_delay}s")
            return default_delay

    except Exception as e:
        logger.warning(f"Failed to parse retry delay from error message: {str(e)}. Using default delay: {default_delay}s")
        return default_delay

class GeminiHandler:
    """
    Handles document processing and Gemini API interaction.
    Delays are now only applied reactively on 429 errors.
    Defaults to using the gemini-2.0-flash model.
    """

    def __init__(self, case_id: str, case_type: str):
        """
        Initialize the Gemini handler.

        Args:
            case_id: The case ID to process
            case_type: The case type to differentiate system prompts
        """
        self.case_id = case_id
        self.case_type = case_type
        self.temp_dir = None
        self.api_key = os.getenv("GOOGLE_API_KEY")

        # --- Set gemini-2.0-flash as the default model ---
        self.model_name = os.getenv("GEMINI_MODEL")

        if not self.api_key:
            raise ValueError("Missing Google API key. Set GOOGLE_API_KEY in the environment variables.")

        # Configure Gemini API
        genai.configure(api_key=self.api_key)

        # Initialize MongoDB connection
        if MongoDBConnection is None:
            raise RuntimeError("MongoDBConnection could not be imported. Check import paths and dependencies.")
        try:
            self.mongo_connection = MongoDBConnection()
            self.db = self.mongo_connection.get_database()
            # Check if db connection itself failed
            if self.db is None:
                raise RuntimeError("Failed to get database from MongoDB connection.")
            self.collection = self.db["case_add"]  # Ensure collection name matches CRUDUtils/router
            # Initialize system_prompts collection reference
            self.prompts_collection = self.db["system_prompts"]
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB connection or get collection: {e}")
            raise RuntimeError(f"Failed to initialize MongoDB connection: {e}") from e

        # Azure Blob Storage configuration
        self.connection_string = os.getenv("AZURE_CONNECTION_STRING")
        if not self.connection_string:
            raise ValueError("AZURE_CONNECTION_STRING not set in environment variables")
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        except Exception as e:
            logger.error(f"Failed to create Azure BlobServiceClient: {e}")
            raise ValueError(f"Failed to initialize Azure connection: {e}") from e

        self.container_name = os.getenv("AZURE_CONTAINER_NAME", "original-data")  # Use env var for container name

        # Load system prompts from MongoDB
        self.system_prompts = self.load_system_prompts_from_db()

        logger.info(f"Initialized GeminiHandler for case_id: {case_id} with model {self.model_name}")

    def load_system_prompts_from_db(self) -> dict:
        """
        Load system prompts from MongoDB.
        Returns a dictionary mapping sections to their prompts.
        """
        try:
            # Query all prompts from the system_prompts collection

            # Log the collection name and database to help with debugging
            logger.info(f"Attempting to load prompts from collection: {self.prompts_collection.name} in database: {self.prompts_collection.database.name}")

            # Count documents to verify collection has data
            count = self.prompts_collection.count_documents({})
            logger.info(f"Found {count} documents in system_prompts collection")

            # Try a direct query for a specific document to verify we can access the collection
            test_doc = self.prompts_collection.find_one({})
            if test_doc:
                logger.info(f"Successfully retrieved a test document with keys: {list(test_doc.keys())}")
            else:
                logger.warning("Could not retrieve a test document from the collection")

            # Get all prompts
            prompts = list(self.prompts_collection.find())
            logger.info(f"Retrieved {len(prompts)} documents from system_prompts collection")

            if not prompts:
                logger.warning("No system prompts found in MongoDB. Using default prompts.")
                return self.get_default_prompts()

            # Format as a dictionary with section as key and prompt text as value
            result = {}

            # Log the structure of the first prompt to help with debugging
            if prompts and len(prompts) > 0:
                logger.info(f"First prompt structure: {list(prompts[0].keys())}")
                logger.info(f"First prompt case_type: {prompts[0].get('case_type', 'Not specified')}")

            for prompt in prompts:
                try:
                    # Get the case type from the document
                    case_type = prompt.get("case_type", "")
                    logger.info(f"Processing prompt with case_type: {case_type}")

                    # Process each field that could be a section
                    for key, value in prompt.items():
                        # Skip non-section fields
                        if key in ["_id", "case_type", "description", "prompt_id", "id"]:
                            continue

                        # Use the field name as the section key
                        section_key = key

                        # Log the section key to help with debugging
                        logger.info(f"Found section key: {section_key} in prompt")

                        # If this prompt's case_type matches the current case_type, add a case-specific key
                        if case_type and case_type == self.case_type:
                            case_specific_key = f"{section_key}_{self.case_type}"
                            result[case_specific_key] = value
                            logger.info(f"Added case-specific prompt for '{case_specific_key}'")

                        # Always add the generic section key too
                        result[section_key] = value
                        logger.info(f"Added generic prompt for '{section_key}'")

                        # Also add version with spaces instead of underscores
                        if "_" in section_key:
                            space_key = section_key.replace("_", " ")
                            result[space_key] = value
                            logger.info(f"Added prompt with spaces for '{space_key}'")
                except Exception as prompt_error:
                    logger.error(f"Error processing prompt: {prompt_error}")
                    continue

            # If we still have no prompts, use default prompts
            if not result:
                logger.warning("No valid prompts found in MongoDB. Using default prompts.")
                return self.get_default_prompts()

            logger.info(f"Loaded {len(result)} system prompts from MongoDB")
            logger.info(f"Available prompt keys: {list(result.keys())}")
            return result

        except Exception as e:
            logger.error(f"Error loading system prompts from MongoDB: {e}")
            # Fallback to file-based prompts if MongoDB fails
            return self.load_system_prompts_from_file()

    def load_system_prompts_from_file(self) -> dict:
        """
        Fallback method to load system prompts from a JSON file.
        Returns a dictionary mapping sections to their prompts.
        """
        SYSTEM_PROMPTS_FILE = "src/controller/system_prompts.json"

        if not os.path.exists(SYSTEM_PROMPTS_FILE):
            logger.warning(f"System prompts file '{SYSTEM_PROMPTS_FILE}' not found. Using default prompts.")
            return self.get_default_prompts()

        try:
            logger.info(f"Loading system prompts from file: {SYSTEM_PROMPTS_FILE}")
            with open(SYSTEM_PROMPTS_FILE, "r", encoding='utf-8') as f:
                file_content = json.load(f)

            # Convert the JSON structure to our format
            result = {}

            # Process each case type
            for case_type, sections in file_content.items():
                logger.info(f"Processing case type: {case_type}")

                # Process each section
                for section_name, section_content in sections.items():
                    # Use the section name as the key
                    section_key = section_name

                    # Add the section content to the result
                    result[section_key] = section_content
                    logger.info(f"Added prompt for section: {section_key}")

                    # If this case type matches the current case type, add a case-specific key
                    if case_type == self.case_type:
                        case_specific_key = f"{section_key}_{self.case_type}"
                        result[case_specific_key] = section_content
                        logger.info(f"Added case-specific prompt for: {case_specific_key}")

            logger.info(f"Loaded {len(result)} prompts from file")
            logger.info(f"Available prompt keys: {list(result.keys())}")
            return result

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in '{SYSTEM_PROMPTS_FILE}'. Using default prompts.")
            return self.get_default_prompts()
        except Exception as e:
            logger.error(f"Error loading system prompts from '{SYSTEM_PROMPTS_FILE}': {e}")
            return self.get_default_prompts()

    def get_default_prompts(self) -> Dict[str, str]:
        """
        Get default prompts when no prompts are found in MongoDB or file.

        Returns:
            A dictionary of default prompts.
        """
        logger.info("Using default prompts")

        # Define some basic default prompts for critical sections
        default_prompts = {
            "Background_Information": "Analyze the provided documents and extract key background information for the case.",
            "Site_Inspection": "Analyze the provided documents and extract information about the site inspection.",
            "Discussion": "Analyze the provided documents and provide a discussion of the findings.",
            "Summary_of_Opinions": "Analyze the provided documents and summarize the key opinions.",
            "Conclusion": "Analyze the provided documents and provide a conclusion.",
            "Exhibits": "Analyze the provided documents and list any exhibits."
        }

        # Also add the keys without underscores for compatibility
        for key, value in list(default_prompts.items()):
            new_key = key.replace("_", " ")
            default_prompts[new_key] = value

        logger.info(f"Created {len(default_prompts)} default prompts")
        logger.info(f"Default prompt keys: {list(default_prompts.keys())}")
        return default_prompts

    def set_model(self, model_name: str):
        self.model_name = model_name

    def get_case_documents(self) -> List[str]:
        """
        Retrieve document paths for the given case ID from MongoDB.
        Looks for paths primarily in the 'pdf' list within the case document.
        """
        if self.collection is None:
            logger.error("MongoDB collection is not initialized in GeminiHandler.")
            raise RuntimeError("MongoDB collection not initialized.")

        try:
            case_data = self.collection.find_one({"case_id": self.case_id})
        except Exception as e:
            logger.error(f"Error querying MongoDB for case {self.case_id}: {e}")
            raise RuntimeError(f"Database query failed for case {self.case_id}: {e}") from e

        if not case_data:
            logger.error(f"No case data found in MongoDB for case ID: {self.case_id}")
            return []  # Return empty list if no case data is found

        doc_paths = []
        if "pdf" in case_data and isinstance(case_data["pdf"], list):
            for item in case_data["pdf"]:
                if isinstance(item, dict) and "file_path" in item and item["file_path"]:
                    doc_paths.append(item["file_path"])
                elif isinstance(item, str) and item:
                    doc_paths.append(item)
                else:
                    logger.warning(f"Skipping invalid or missing file_path in pdf item for case {self.case_id}: {item}")

        logger.info(f"Found {len(doc_paths)} document paths for case {self.case_id}")
        return doc_paths

    def download_case_documents(self) -> str:
        """
        Download documentation files from Azure into a temp directory for processing.
        """
        if self.temp_dir and os.path.exists(self.temp_dir):
            logger.warning(f"Temporary directory {self.temp_dir} already exists. Cleaning up before creating a new one.")
            self.cleanup()
        try:
            self.temp_dir = tempfile.mkdtemp(prefix=f"case_{self.case_id}_")
            logger.info(f"Created temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Failed to create temporary directory: {e}")
            raise RuntimeError(f"Failed to create temporary directory: {e}") from e

        try:
            doc_paths = self.get_case_documents()
        except (ValueError, RuntimeError) as e:
            logger.error(f"Cannot download documents as paths could not be retrieved: {e}")
            return self.temp_dir

        if not doc_paths:
            logger.warning(f"No document paths retrieved for case {self.case_id}. No files will be downloaded.")
            return self.temp_dir

        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
        except Exception as e:
            logger.error(f"Failed to get Azure container client for '{self.container_name}': {e}")
            return self.temp_dir

        downloaded_files_count = 0
        for doc_path in doc_paths:
            if not doc_path or not isinstance(doc_path, str):
                logger.warning(f"Skipping invalid document path: {doc_path}")
                continue

            normalized_path = doc_path.replace("\\", "/").strip("/")
            if not normalized_path:
                logger.warning(f"Skipping empty normalized path derived from: {doc_path}")
                continue

            file_name = os.path.basename(normalized_path)
            if not file_name:
                logger.warning(f"Could not determine filename from path: {normalized_path}. Skipping.")
                continue
            local_file_path = os.path.join(self.temp_dir, file_name)

            try:
                blob_client = container_client.get_blob_client(blob=normalized_path)

                if not blob_client.exists():
                    logger.warning(f"Blob not found in Azure: container='{self.container_name}', blob='{normalized_path}'")
                    continue

                with open(local_file_path, "wb") as file:
                    blob_data = blob_client.download_blob()
                    blob_data.readinto(file)

                if os.path.exists(local_file_path) and os.path.getsize(local_file_path) > 0:
                    logger.info(f"Successfully downloaded: {normalized_path} -> {local_file_path}")
                    downloaded_files_count += 1
                else:
                    logger.warning(f"Downloaded file is missing or empty: {local_file_path}")
                    if os.path.exists(local_file_path):
                        try:
                            os.remove(local_file_path)
                        except OSError:
                            pass

            except Exception as e:
                logger.error(f"Error downloading Azure blob '{normalized_path}': {str(e)}")
                if os.path.exists(local_file_path):
                    try:
                        os.remove(local_file_path)
                    except OSError:
                        pass

        logger.info(f"Downloaded {downloaded_files_count} out of {len(doc_paths)} specified files for case {self.case_id}.")
        return self.temp_dir

    def get_file_list(self, directory: str) -> tuple:
        """
        Returns lists of PDF, DOCX, and TXT files found in the specified directory.
        """
        if not directory or not os.path.isdir(directory):
            logger.error(f"Directory not found or invalid for listing files: {directory}")
            return [], [], []
        try:
            p = Path(directory)
            pdf_files = [str(f) for f in p.glob("*.pdf")]
            docx_files = [str(f) for f in p.glob("*.docx")]
            txt_files = [str(f) for f in p.glob("*.txt")]
            logger.info(f"Found {len(pdf_files)} PDF, {len(docx_files)} DOCX, {len(txt_files)} TXT files in {directory}")
            return pdf_files, docx_files, txt_files
        except Exception as e:
            logger.error(f"Error listing files in directory {directory}: {e}")
            return [], [], []

    def process_pdf_for_gemini(self, pdf_path: str) -> Optional[Dict]:
        """
        Convert PDF to text for Gemini processing.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF (fitz) is not installed. Cannot process PDF files. Run 'pip install PyMuPDF'")
            return None

        if not pdf_path or not os.path.exists(pdf_path):
            logger.error(f"PDF file not found or path invalid: {pdf_path}")
            return None

        try:
            doc = fitz.open(pdf_path)
            text_content = ""
            for page_num, page in enumerate(doc):
                try:
                    page_text = page.get_text()
                    if page_text:
                        text_content += page_text
                except Exception as page_e:
                    logger.warning(f"Error extracting text from page {page_num + 1} of {pdf_path}: {page_e}")
                    text_content += f"\n[Error extracting page {page_num + 1}]\n"
            doc.close()

            processed_text = text_content.strip()
            if not processed_text:
                logger.warning(f"No text extracted from PDF: {pdf_path}")
                return None

            logger.info(f"Successfully extracted text from PDF: {os.path.basename(pdf_path)}")
            return {"text": processed_text}

        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            return None

    def process_docx(self, docx_path: str) -> Optional[Dict]:
        """
        Convert DOCX to text for Gemini processing.
        """
        try:
            import docx
        except ImportError:
            logger.error("python-docx is not installed. Cannot process DOCX files. Run 'pip install python-docx'")
            return None

        if not docx_path or not os.path.exists(docx_path):
            logger.error(f"DOCX file not found or path invalid: {docx_path}")
            return None

        try:
            doc = docx.Document(docx_path)
            full_text = [para.text for para in doc.paragraphs]
            text_content = "\n\n".join(p for p in full_text if p.strip())
            processed_text = text_content.strip()
            if not processed_text:
                logger.warning(f"No text extracted from DOCX: {docx_path}")
                return None

            logger.info(f"Successfully processed DOCX: {os.path.basename(docx_path)}")
            return {"text": processed_text}
        except Exception as e:
            logger.error(f"Error processing DOCX {docx_path}: {str(e)}")
            return None

    def process_txt(self, txt_path: str) -> Optional[Dict]:
        """
        Convert a TXT file to text for Gemini processing.
        """
        if not txt_path or not os.path.exists(txt_path):
            logger.error(f"TXT file not found or path invalid: {txt_path}")
            return None

        try:
            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                text_content = f.read()

            processed_text = text_content.strip()
            if not processed_text:
                logger.warning(f"No text extracted from TXT: {txt_path}")
                return None

            logger.info(f"Successfully processed TXT: {os.path.basename(txt_path)}")
            return {"text": processed_text}
        except Exception as e:
            logger.error(f"Error processing TXT {txt_path}: {str(e)}")
            return None

    def process_documents_in_batches(self, max_batch_size: int = 5) -> List[List[Dict]]:
        """
        Download, process (PDF, DOCX, TXT), and group results into smaller batches.
        """
        all_content = []
        temp_documents_dir = None
        try:
            temp_documents_dir = self.download_case_documents()
            if not temp_documents_dir or not os.path.exists(temp_documents_dir):
                logger.warning(f"Could not download or access docs directory for case {self.case_id}.")
                return []

            pdf_files, docx_files, txt_files = self.get_file_list(temp_documents_dir)
            if not pdf_files and not docx_files and not txt_files:
                logger.warning(f"No PDF, DOCX, or TXT found for case {self.case_id}")
                return []

            for pdf_file in pdf_files:
                content = self.process_pdf_for_gemini(pdf_file)
                if content:
                    all_content.append(content)

            for docx_file in docx_files:
                content = self.process_docx(docx_file)
                if content:
                    all_content.append(content)

            for txt_file in txt_files:
                content = self.process_txt(txt_file)
                if content:
                    all_content.append(content)

            if not all_content:
                logger.warning(f"No textual content extracted for case {self.case_id}.")
                return []

            batches = [all_content[i:i + max_batch_size] for i in range(0, len(all_content), max_batch_size)]
            logger.info(f"Prepared {len(batches)} batch(es) for case {self.case_id}.")
            return batches
        except Exception as e:
            logger.error(f"Error processing documents for case {self.case_id}: {e}", exc_info=True)
            raise

    def create_unified_analysis(
        self,
        section: str,
        batch_size: int = 3,
        base_retry_delay: int = 5,
        max_retries: int = 3
    ) -> str:
        """
        Creates a unified analysis by processing documents in batches
        and synthesizing a final summary from Gemini.
        """
        try:
            batches = self.process_documents_in_batches(max_batch_size=batch_size)
            if not batches:
                return "Error: No documents found or processed successfully for this case."
            print("<----------Here is the section-------------->",section)
            batch_results = []
            processing_failed = False
            for i, batch in enumerate(batches):
                logger.info(f"Processing batch {i + 1} of {len(batches)} for section '{section}'")
                response = self.query_with_batch(batch, section, base_retry_delay, max_retries)
                logger.info(f"Response from batch {i + 1}: {response}")
                if response.startswith("Error:"):
                    logger.error(f"Batch {i + 1} failed: {response}")
                    batch_results.append(f"[[ERROR PROCESSING BATCH {i + 1}: {response}]]")
                    processing_failed = True
                else:
                    batch_results.append(response)

            if len(batch_results) == 1 and not processing_failed:
                return batch_results[0]

            combined_text = ""
            for idx, result in enumerate(batch_results):
                combined_text += f"--- ANALYSIS FROM BATCH {idx + 1} ---\n{result}\n--- END OF BATCH {idx + 1} ---\n\n"

            model = genai.GenerativeModel(self.model_name)
            failure_warning = ""
            if processing_failed:
                failure_warning = "IMPORTANT: Some batches encountered errors, so the final result may be incomplete.\n\n"

            synthesis_prompt = f"""
                {failure_warning}You are provided with analyses generated from different batches. Some batches may contain errors.
                Focus on the section: '{section}'

                IMPORTANT FORMATTING INSTRUCTIONS:
                - If you are generating content for the "Background Information" section and you find any content related to "Findings", you MUST separate them.
                - Place all findings content under a "**1.4 Findings**" header BEFORE the background information.
                - Place all background information under a "**2.0 Background Information**" header.
                - Make sure these sections are clearly separated.

                Instructions:
                1. Synthesize the successful analyses into a coherent, consolidated report.
                2. If some batches had errors, do not mention these errors or the failed batches in your final report(e.g., "ERROR: Could not process batch",• Note: Analysis from one batch was incomplete.).
                3. Omit repeated or conflicting details. If there's a contradiction you cannot resolve, highlight it gently.
                4. Do not include the '--- ANALYSIS FROM BATCH...' markers or the error messages themselves, but you can mention missing data explicitly.
                5. Start the final output with the formal content. Avoid extraneous text.
                6. Do not provide any unnecessary data like the font type used or font size used like this **<font face="Times New Roman" size="4">**SUMMARY**</font>** or the ariel font name.
                7. Do not add the section in which the content is not available.
                8. For user-provided reports like weather reports, generate a concise overall summary highlighting key findings or conditions. Do not provide a granular, step-by-step, or day-by-day breakdown.
                9. Use the proper Markdown format for the report. This is very important.
                10. ALWAYS place findings content BEFORE background information content.
                11. Include subsections only if they contain meaningful content. If a subsection (e.g., "Improper Stormwater Drainage" or "Excessive Slope/Cross-Slope") has no substantive information or only indicates lack of data, do not include the subsection or any placeholder text (e.g., “was not indicated as a contributing factor”). Simply omit it entirely.
                12. If the references are taken from .rpt do not include the reference number in the final output like no not do this (If files with the.rpt extension are provided, treat them as reference only (e.g., for format, different case context). Do not extract content from them or use it in the response The report details the investigation into the circumstances surrounding).

                Collected Batches:
                {combined_text}

                Now provide the final consolidated analysis for '{section}':
                """

            retry_count = 0
            while retry_count <= max_retries:
                try:
                    unified_response = model.generate_content(
                        [synthesis_prompt],
                        generation_config=genai.GenerationConfig(
                            temperature=0.2,
                            max_output_tokens=8192
                        ),
                        request_options={"timeout": 300}
                    )
                    if hasattr(unified_response, "prompt_feedback") and unified_response.prompt_feedback and unified_response.prompt_feedback.block_reason:
                        return f"Error: Content generation blocked ({unified_response.prompt_feedback.block_reason})"
                    if not hasattr(unified_response, "text") or not unified_response.text:
                        finish_reason = unified_response.candidates[0].finish_reason if unified_response.candidates else "UNKNOWN"
                        return f"Error: No text returned from final synthesis (Reason: {finish_reason})."
                    return unified_response.text
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "rate limit" in error_str.lower():
                        retry_delay = extract_retry_delay(error_str, default_delay=base_retry_delay * (2 ** retry_count))
                        logger.warning(f"Rate limit in final synthesis. Sleeping {retry_delay}s.")
                        time.sleep(retry_delay)
                        retry_count += 1
                    else:
                        logger.error(f"Final synthesis failed: {error_str}")
                        raise
            return "Error: Could not create unified analysis due to repeated rate limit or other errors."
        finally:
            self.cleanup()

    def query_with_batch(
        self,
        batch: List[Dict],
        section: str,
        base_retry_delay: int,
        max_retries: int
    ) -> str:
        """
        Processes a single document batch with a system prompt for the specified section.
        """
        if not batch:
            return "Error: Empty batch provided for querying."

        # Get system prompt for the section
        system_prompt_text = None

        # First try case-type specific prompt
        if self.case_type:
            section_key = f"{section}_{self.case_type}"
            system_prompt_text = self.system_prompts.get(section_key)
            if system_prompt_text:
                logger.info(f"Using case-type specific prompt for '{section_key}'")

        # Fall back to generic section prompt
        if not system_prompt_text:
            system_prompt_text = self.system_prompts.get(section)
            logger.info(f"Using generic prompt for section '{section}'")

        # If still no prompt, try to find a similar key or use a default prompt
        if not system_prompt_text:
            # Log available prompt keys to help with debugging
            available_keys = list(self.system_prompts.keys())
            logger.error(f"No system prompt found for section '{section}'. Available keys: {available_keys}")

            # Check if there's a similar key with different capitalization or formatting
            for key in available_keys:
                if section.lower() in key.lower() or key.lower() in section.lower():
                    logger.info(f"Found similar key: '{key}' that might match '{section}'")
                    system_prompt_text = self.system_prompts.get(key)
                    if system_prompt_text:
                        logger.info(f"Using prompt from similar key: '{key}'")
                        break

            # Try with underscores instead of spaces
            if not system_prompt_text:
                section_with_underscores = section.replace(" ", "_")
                if section_with_underscores in self.system_prompts:
                    system_prompt_text = self.system_prompts.get(section_with_underscores)
                    logger.info(f"Using prompt from key with underscores: '{section_with_underscores}'")

            # Try with spaces instead of underscores
            if not system_prompt_text:
                section_with_spaces = section.replace("_", " ")
                if section_with_spaces in self.system_prompts:
                    system_prompt_text = self.system_prompts.get(section_with_spaces)
                    logger.info(f"Using prompt from key with spaces: '{section_with_spaces}'")

            # If still no prompt, use a generic default prompt
            if not system_prompt_text:
                logger.warning(f"No matching prompt found for section '{section}'. Using generic default prompt.")
                system_prompt_text = f"Analyze the provided documents and extract information for the '{section}' section of the report."
                logger.info(f"Created generic default prompt for section: {section}")

        system_prompt = {"text": system_prompt_text}
        contents = batch + [system_prompt]

        # Validate batch format for Gemini API
        for i, item in enumerate(contents):
            # Ensure each item has only the 'text' key
            if not isinstance(item, dict) or 'text' not in item or len(item) != 1:
                logger.warning(f"Invalid item format at index {i}: {item}")
                # Fix the item format
                if isinstance(item, dict) and 'text' in item:
                    # Keep only the 'text' key
                    contents[i] = {"text": item['text']}
                    logger.info(f"Fixed item format at index {i}")
                else:
                    logger.error(f"Cannot fix item format at index {i}, removing from batch")
                    # Remove the item if it can't be fixed
                    contents.pop(i)

        model = genai.GenerativeModel(self.model_name)
        retry_count = 0
        while retry_count <= max_retries:
            try:
                response = model.generate_content(
                    contents,
                    generation_config=genai.GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=8192
                    ),
                    request_options={"timeout": 300}
                )
                if hasattr(response, "prompt_feedback") and response.prompt_feedback and response.prompt_feedback.block_reason:
                    return f"Error: Content generation blocked ({response.prompt_feedback.block_reason})"
                if not hasattr(response, "text") or not response.text:
                    finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                    return f"Error: No text returned (Reason: {finish_reason})."
                return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
                    retry_delay = extract_retry_delay(error_str, default_delay=base_retry_delay * (2 ** retry_count))
                    logger.warning(f"Rate limit in batch query. Sleeping {retry_delay}s.")
                    time.sleep(retry_delay)
                    retry_count += 1
                elif "Unable to determine the intended type of the `dict`" in error_str:
                    # Handle format error
                    logger.error(f"Format error in batch: {error_str}")
                    # Try to fix the batch format
                    for i, item in enumerate(contents):
                        contents[i] = {"text": str(item) if not isinstance(item, dict) or 'text' not in item else item['text']}
                    logger.info("Attempted to fix batch format, retrying...")
                    retry_count += 1
                else:
                    logger.error(f"Gemini query error: {error_str}")
                    raise RuntimeError(f"Gemini query failed: {error_str}") from e
        return "Error: Rate limit exceeded after maximum retries."

    def cleanup(self):
        """
        Clean up the temporary directory if it exists.
        """
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up temporary directory {self.temp_dir}: {e}")
            finally:
                self.temp_dir = None

    def Image_processing(self, image_b64: str) -> str:
        """
        Takes a base64 encoded image, saves it to the 'uploads/images' directory, then
        uses Google's generative AI to generate a concise descriptive caption. The file is left
        in uploads/images after processing.
        """
        import base64
        import time
        import google.generativeai as genai

        image_model = os.getenv("GEMINI_IMAGE_MODEL")

        # Create uploads/images directory if it doesn't exist
        save_dir = os.path.join("uploads", "images")
        print("Here is the imagewazxfghjk",save_dir)
        os.makedirs(save_dir, exist_ok=True)

        # Decode the image from base64
        try:
            decoded_image = base64.b64decode(image_b64)
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            return f"Error: Invalid base64 image data. {e}"

        # Generate a unique filename based on the current timestamp
        timestamp_str = str(int(time.time()))
        file_name = f"image_{timestamp_str}.jpg"
        tmp_file_path = os.path.join(save_dir, file_name)

        # Save the decoded image to the uploads/images folder
        try:
            with open(tmp_file_path, "wb") as f:
                f.write(decoded_image)
        except Exception as e:
            logger.error(f"Failed to save image to {tmp_file_path}: {e}")
            return f"Error: Could not save image. {e}"

        max_retries = 3
        base_delay = 5
        attempt = 0

        while attempt < max_retries:
            # Configure Gemini API
            genai.configure(api_key=self.api_key)
            try:
                with open(tmp_file_path, "rb") as image_file:
                    image_bytes = image_file.read()

                # Create the model
                model = genai.GenerativeModel(image_model)

                # Generate content with the image
                response = model.generate_content([
                    {"mime_type": "image/jpeg", "data": image_bytes},
                    "Act as an expert in Forensic Engineering with decades of experience in analyzing complex incidents, conducting site inspections, and generating detailed engineering reports.\n\nDo not include any introductory or explanatory text about your role or what you are doing. Begin directly with the description of the image, Do not invent information."
                ])

                if hasattr(response, 'prompt_feedback') and response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
                    logger.warning(f"Image description blocked: {response.prompt_feedback.block_reason}")
                    return "Content was blocked by the model."

                if not hasattr(response, "text") or not response.text:
                    logger.warning("Image description returned empty text.")
                    return "No description generated."

                return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate limit" in error_str.lower():
                    time.sleep(base_delay * (2 ** attempt))
                    attempt += 1
                else:
                    logger.error(f"Error describing image: {error_str}")
                    return f"Error generating image description: {error_str}"

        return "Error: Repeated rate limit or network errors prevented generating image description."

def __del__(self):
        """
        Ensure cleanup when the object is garbage collected.
        """
        if hasattr(self, "case_id"):
            logger.debug(f"GeminiHandler instance for case {self.case_id} is being deleted. Running cleanup.")
        self.cleanup()


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Process case documents with Gemini for unified analysis')
    parser.add_argument('--case_id', type=str, required=True, help='Case ID to process')
    parser.add_argument('--section', type=str, required=True, help='Section identifier for analysis (e.g., "background", "analysis")')
    parser.add_argument('--case_type', type=str, required=True, help='Case Type to process')
    parser.add_argument('--model', type=str, default="gemini-2.5-flash-preview-04-17", help='Gemini model to use (default: gemini-2.0-flash)')
    parser.add_argument('--batch_size', type=int, default=3, help='Maximum docs per batch (default: 3)')
    parser.add_argument('--base_retry_delay', type=int, default=5, help='Base seconds for backoff (default: 5)')
    parser.add_argument('--max_retries', type=int, default=3, help='Max retries on rate limits (default: 3)')

    args = parser.parse_args()
    try:
        handler = GeminiHandler(args.case_id, args.case_type)
        if args.model:
            handler.set_model(args.model)

        print(f"\nProcessing case {args.case_id}, section '{args.section}' with model {handler.model_name}.")
        print(f"Batch size: {args.batch_size}, base retry delay: {args.base_retry_delay}, max retries: {args.max_retries}")

        if args.section == "14_findings_and_background":
            out14 = handler.create_unified_analysis(
                section="1.4 Findings",
                batch_size=args.batch_size,
                base_retry_delay=args.base_retry_delay,
                max_retries=args.max_retries
            )
            outBackground = handler.create_unified_analysis(
                section="Background Information",
                batch_size=args.batch_size,
                base_retry_delay=args.base_retry_delay,
                max_retries=args.max_retries
            )
            response = f"=== 1.4 FINDINGS ===\n{out14}\n\n=== BACKGROUND INFORMATION ===\n{outBackground}"
        else:
            response = handler.create_unified_analysis(
                section=args.section,
                batch_size=args.batch_size,
                base_retry_delay=args.base_retry_delay,
                max_retries=args.max_retries
            )

        print("\n===== GEMINI UNIFIED RESPONSE =====")
        if response.startswith("Error:") or "blocked" in response:
            print(f"Processing Result: {response}")
        else:
            print(response)
        print("===================================")

    except (ValueError, RuntimeError) as e:
        print(f"\nError during initialization or processing: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    sys.exit(0)
