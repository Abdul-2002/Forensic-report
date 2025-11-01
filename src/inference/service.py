"""
Inference service for the application.
"""
import base64
import glob
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests

from src.core.config import UPLOAD_DIR
from src.core.logging_config import get_logger
from src.db.repositories.case_repository import CaseRepository
from src.inference.exceptions import InferenceError, APIRateLimitError, APIError
from src.inference.loader import model_loader
from src.inference.models.gemini_model import GeminiModel
from src.inference.postprocessing import convert_pdf_to_images, extract_findings_and_background
from src.inference.preprocessing import process_pdf_for_gemini, process_docx, process_txt
from src.utils.file_helpers import upload_to_azure

logger = get_logger(__name__)

# The generate_embeddings function has been removed as it's no longer needed with the Gemini approach

class InferenceService:
    """
    Inference service for the application.
    """

    def __init__(self, case_id: str, case_type: str = "case_type_1"):
        """
        Initialize the inference service.

        Args:
            case_id: The case ID.
            case_type: The case type.
        """
        self.case_id = case_id
        self.case_type = case_type
        self.temp_dir = None
        self.case_repo = CaseRepository()

        # Load system prompts
        self.system_prompts = self.load_system_prompts()

    def load_system_prompts(self) -> Dict[str, str]:
        """
        Load system prompts from the database only.

        Returns:
            A dictionary of system prompts.
        """
        try:
            # Try to load from database
            prompts_collection = self.case_repo.db["system_prompts"]

            # Log the collection name and database to help with debugging
            logger.info(f"Attempting to load prompts from collection: {prompts_collection.name} in database: {self.case_repo.db.name}")

            # Count documents to verify collection has data
            count = prompts_collection.count_documents({})
            logger.info(f"Found {count} documents in system_prompts collection")

            # Try a direct query for a specific document to verify we can access the collection
            test_doc = prompts_collection.find_one({})
            if test_doc:
                logger.info(f"Successfully retrieved a test document with keys: {list(test_doc.keys())}")
            else:
                logger.warning("Could not retrieve a test document from the collection")
                return {}

            # Get all prompts
            prompts = list(prompts_collection.find())
            logger.info(f"Retrieved {len(prompts)} documents from system_prompts collection")

            if not prompts:
                logger.warning("No system prompts found in MongoDB.")
                return {}

            # Format as a dictionary with section as key and prompt text as value
            result = {}

            # Log the structure of the first prompt to help with debugging
            if prompts and len(prompts) > 0:
                logger.info(f"First prompt structure: {list(prompts[0].keys())}")
                logger.info(f"First prompt case_type: {prompts[0].get('case_type', 'Not specified')}")

            # Create a mapping of case types for fuzzy matching
            case_type_mapping = {}
            for prompt in prompts:
                case_type = prompt.get("case_type", "")
                if case_type:
                    case_type_mapping[case_type.lower()] = case_type

            logger.info(f"Available case types in MongoDB: {list(case_type_mapping.keys())}")

            # Find the best match for the current case type
            best_match = None
            if self.case_type:
                current_case_type_lower = self.case_type.lower()
                # Exact match
                if current_case_type_lower in case_type_mapping:
                    best_match = case_type_mapping[current_case_type_lower]
                    logger.info(f"Found exact case type match: {best_match}")
                # Partial match
                else:
                    for db_case_type_lower, original_case_type in case_type_mapping.items():
                        # Check if the current case type contains the DB case type or vice versa
                        if db_case_type_lower in current_case_type_lower or current_case_type_lower in db_case_type_lower:
                            best_match = original_case_type
                            logger.info(f"Found partial case type match: '{self.case_type}' matches with '{best_match}'")
                            break

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

                        # If this prompt's case_type matches the best match for the current case_type, add a case-specific key
                        if case_type and best_match and case_type == best_match:
                            case_specific_key = f"{section_key}_{self.case_type}"
                            result[case_specific_key] = value
                            logger.info(f"Added case-specific prompt for '{case_specific_key}' (matched from '{best_match}')")

                        # Always add the generic section key
                        # This ensures we have fallback prompts available
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

            logger.info(f"Loaded {len(result)} system prompts from MongoDB")
            logger.info(f"Available prompt keys: {list(result.keys())}")
            return result

        except Exception as e:
            logger.error(f"Error loading system prompts from MongoDB: {e}")
            return {}



    def get_case_documents(self) -> List[str]:
        """
        Retrieve document paths for the given case ID from MongoDB.

        Returns:
            A list of document paths.
        """
        case_data = self.case_repo.get_by_case_id(self.case_id)
        if not case_data:
            logger.error(f"No case data found in MongoDB for case ID: {self.case_id}")
            return []

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

    async def download_case_documents(self) -> str:
        """
        Download documentation files from Azure into a temp directory for processing.

        Returns:
            The path to the temporary directory.
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

        # Get Azure connection from case repository
        from azure.storage.blob import BlobServiceClient
        from src.core.config import AZURE_CONNECTION_STRING, AZURE_CONTAINER_NAME

        try:
            blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
            container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
        except Exception as e:
            logger.error(f"Failed to get Azure container client for '{AZURE_CONTAINER_NAME}': {e}")
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
                    logger.warning(f"Blob not found in Azure: container='{AZURE_CONTAINER_NAME}', blob='{normalized_path}'")
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

        Args:
            directory: The directory to search for files.

        Returns:
            A tuple of (pdf_files, docx_files, txt_files).
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

    async def process_documents_in_batches(self, max_batch_size: int = 5) -> List[List[Dict]]:
        """
        Download, process (PDF, DOCX, TXT), and group results into smaller batches.

        Args:
            max_batch_size: The maximum number of documents per batch.

        Returns:
            A list of batches, where each batch is a list of document contents.
        """
        all_content = []
        temp_documents_dir = None

        try:
            temp_documents_dir = await self.download_case_documents()
            if not temp_documents_dir or not os.path.exists(temp_documents_dir):
                logger.warning(f"Could not download or access docs directory for case {self.case_id}.")
                return []

            pdf_files, docx_files, txt_files = self.get_file_list(temp_documents_dir)
            if not pdf_files and not docx_files and not txt_files:
                logger.warning(f"No PDF, DOCX, or TXT found for case {self.case_id}")
                return []

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
                logger.warning(f"No textual content extracted for case {self.case_id}.")
                return []

            batches = [all_content[i:i + max_batch_size] for i in range(0, len(all_content), max_batch_size)]
            logger.info(f"Prepared {len(batches)} batch(es) for case {self.case_id} with case_type '{self.case_type}'.")
            return batches
        except Exception as e:
            logger.error(f"Error processing documents for case {self.case_id}: {e}", exc_info=True)
            raise

    async def create_unified_analysis(
        self,
        section: str,
        batch_size: int = 3,
        base_retry_delay: int = 5,
        max_retries: int = 3
    ) -> str:
        """
        Creates a unified analysis by processing documents in batches
        and synthesizing a final summary from Gemini.

        Args:
            section: The section to analyze.
            batch_size: The maximum number of documents per batch.
            base_retry_delay: The base delay in seconds for retries.
            max_retries: The maximum number of retries.

        Returns:
            The unified analysis text.
        """
        try:
            batches = await self.process_documents_in_batches(max_batch_size=batch_size)
            if not batches:
                return "Error: No documents found or processed successfully for this case."

            batch_results = []
            processing_failed = False

            for i, batch in enumerate(batches):
                logger.info(f"Processing batch {i + 1} of {len(batches)} for section '{section}' with case_type '{self.case_type}'")
                response = await self.query_with_batch(batch, section, base_retry_delay, max_retries)

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

            # Get Gemini model
            model = model_loader.get_model("gemini", "gemini-2.5-flash-preview-04-17")

            failure_warning = ""
            if processing_failed:
                failure_warning = "IMPORTANT: Some batches encountered errors, so the final result may be incomplete.\n\n"

            synthesis_prompt = f"""{failure_warning}You are provided with analyses generated from different text batches. Some batches may contain errors or no relevant information for the requested section. Your task is to synthesize the information from the *successful and relevant* batches.

                    Focus on the section: '{section}'

                    Special Handling for 'Background Information' section:
                    - If the requested `{section}` is 'Background Information', first meticulously scan all `Collected Batches` for any content explicitly labeled or clearly identifiable as 'Findings' (or similar terms like 'Key Observations', 'Conclusions' from the batch analysis related to the background).
                    - If such 'Findings' exist, synthesize them into a dedicated 'Findings' subsection. This 'Findings' subsection should be placed *immediately before* the 'Background Information' content in your final output.
                    - Then, proceed to synthesize the 'Background Information' content itself from all relevant batches.

                    Instructions for Synthesizing '{section}':
                    1.  **Comprehensive Synthesis:** Your primary goal is to create a coherent, consolidated report for the specified `{section}`. Ensure you carefully review and incorporate relevant information from *all* `Collected Batches` that are not explicit error messages and contain data for the `{section}`. Do not arbitrarily omit information from a successful batch.
                    2.  **Error Handling:** If some batches explicitly state an error (e.g., "ERROR: Could not process batch"), do not mention these errors or the failed batches in your final report. Only synthesize content from successfully processed batches.
                    3.  **De-duplication and Conflict Resolution:**
                        *   **Omit Repetition:** Aggressively remove redundant information. If multiple batches state the same fact, include it only once.
                        *   **Avoid Paraphrasing as Distinct Points:** Do not list slightly reworded versions of the same underlying fact or concept as separate bullet points. Strive to capture the core idea once. For example, if one batch says "The pathway was icy" and another says "Ice covered the walkway," these should be consolidated into a single point like "The pathway/walkway was icy."
                        *   **Handle Contradictions:** If there's a direct contradiction you cannot resolve, briefly note the conflicting information (e.g., "Batch A reports X, while Batch B reports Y regarding [topic]."). Avoid this if possible by finding a commonality or more general statement.
                    4.  **Formatting and Cleanliness:**
                        *   **No Markers/Metadata:** Do not include '--- ANALYSIS FROM BATCH...' markers, batch numbers, or any error messages themselves in the final output.
                        *   **Formal Start:** Begin the final output directly with the synthesized content for `{section}`. Avoid introductory phrases like "Here is the analysis..." or other extraneous text.
                        *   **Markdown Usage:** Use only the following Markdown:
                            *   `**Subheading**` for subheadings (e.g., `**Findings**`, `**Background Information**`).
                            *   `*` for bullet points.
                            *   A single `\n` for a new line between distinct pieces of information or after a subheading.
                            *   Do NOT use any other Markdown like font tags (`<font>`), bolding individual words within sentences unless grammatically essential, or HTML.
                    5.  **Content Relevance:**
                        *   **No Empty Sections:** If, after reviewing all batches, no information is found for the requested `{section}`, output nothing or a pre-defined "No information available for this section." message (you'll need to decide how to handle this in your application logic if the LLM outputs nothing).
                        *   **Concise Summaries for Reports:** If the input batches contain user-provided reports (e.g., weather reports, incident reports), generate a concise overall summary highlighting key findings or conditions pertinent to `{section}`. Do not provide a granular, step-by-step, or day-by-day breakdown unless specifically asked for by the nature of `{section}`.
                    6.  **Factually Distinct Bullet Points:** Each bullet point in your final output must represent a *semantically unique* piece of information, condition, or factor. If multiple aspects relate to a single core issue (e.g., various failures in snow/ice management), present them as distinct facets *only if they represent different types of actions, inactions, or observations*. For instance:
                        *   *Good (distinct)*:
                            *   Snow and ice were present on the sidewalk.
                            *   The property owner failed to clear the snow and ice.
                            *   No salt or sand had been applied to the icy sidewalk.
                        *   *Bad (paraphrasing/too granular if not distinct actions/observations)*:
                            *   The sidewalk had snow on it.
                            *   Ice was observed under the snow.
                            *   The concrete surface was slippery due to frozen precipitation.
                        Critically evaluate if points can be combined into a more comprehensive statement without losing distinct factual elements.

                    Collected Batches:
                    {combined_text}

                """

            try:
                unified_response = model.predict(synthesis_prompt, max_retries=max_retries, base_retry_delay=base_retry_delay)
                return unified_response
            except APIRateLimitError:
                return "Error: Could not create unified analysis due to persistent API rate limits."
            except APIError as e:
                return f"Error: {str(e)}"
            except Exception as e:
                logger.error(f"Final synthesis failed: {str(e)}")
                return f"Error: An unexpected error occurred during analysis: {str(e)}"

        finally:
            self.cleanup()

    async def query_with_batch(
        self,
        batch: List[Dict],
        section: str,
        base_retry_delay: int,
        max_retries: int
    ) -> str:
        """
        Processes a single document batch with a system prompt for the specified section.

        Args:
            batch: The batch of documents to process.
            section: The section to analyze.
            base_retry_delay: The base delay in seconds for retries.
            max_retries: The maximum number of retries.

        Returns:
            The analysis text.
        """
        if not batch:
            return "Error: Empty batch provided for querying."

        # Get system prompt for the section
        system_prompt_text = None

        # Normalize section name for lookups
        section_normalized = section.replace(" ", "_")  # With underscores
        section_with_spaces = section_normalized.replace("_", " ")  # With spaces

        # STEP 1: First try case-type specific prompt (highest priority)
        if self.case_type:
            # Try with both underscore and space formats for case-specific prompts
            case_specific_key = f"{section_normalized}_{self.case_type}"
            system_prompt_text = self.system_prompts.get(case_specific_key)

            if not system_prompt_text:
                # Try with spaces in section name
                case_specific_key_spaces = f"{section_with_spaces}_{self.case_type}"
                system_prompt_text = self.system_prompts.get(case_specific_key_spaces)

            if system_prompt_text:
                # Truncate the prompt text if it's too long for logging
                prompt_preview = system_prompt_text[:100] + "..." if len(system_prompt_text) > 100 else system_prompt_text
                logger.info(f"Using case-type specific prompt for '{case_specific_key}': '{prompt_preview}'")
                # Print full prompt for testing
                print(f"here is the full prompt used for section '{section}' with case_type '{self.case_type}': {system_prompt_text}")

        # STEP 2: If no case-specific prompt, try generic section prompt
        if not system_prompt_text:
            # Try with underscores (normalized format)
            system_prompt_text = self.system_prompts.get(section_normalized)

            if system_prompt_text:
                # Truncate the prompt text if it's too long for logging
                prompt_preview = system_prompt_text[:100] + "..." if len(system_prompt_text) > 100 else system_prompt_text
                logger.info(f"Using generic prompt for section '{section_normalized}': '{prompt_preview}'")
                # Print full prompt for testing
                print(f"here is the full prompt used for section '{section_normalized}': {system_prompt_text}")
            else:
                # Try with spaces
                system_prompt_text = self.system_prompts.get(section_with_spaces)

                if system_prompt_text:
                    # Truncate the prompt text if it's too long for logging
                    prompt_preview = system_prompt_text[:100] + "..." if len(system_prompt_text) > 100 else system_prompt_text
                    logger.info(f"Using generic prompt for section '{section_with_spaces}': '{prompt_preview}'")
                    # Print full prompt for testing
                    print(f"here is the full prompt used for section '{section_with_spaces}': {system_prompt_text}")

        # STEP 3: If still no prompt found, try flexible matching
        if not system_prompt_text:
            # If no prompts at all, return error
            if not self.system_prompts:
                logger.error(f"No system prompts found in MongoDB.")
                return "Error: Not enough information is provided. No system prompts found in MongoDB."

            # Log available keys to help with debugging
            available_keys = list(self.system_prompts.keys())
            logger.error(f"No system prompt found for section '{section}'. Available keys: {available_keys}")

            # Try a more flexible matching approach
            for key in available_keys:
                # Check if the key contains the section name or vice versa
                if (section.lower() in key.lower() or
                    key.lower() in section.lower() or
                    section_normalized.lower() in key.lower() or
                    key.lower() in section_normalized.lower()):
                    system_prompt_text = self.system_prompts.get(key)
                    # Truncate the prompt text if it's too long for logging
                    prompt_preview = system_prompt_text[:100] + "..." if len(system_prompt_text) > 100 else system_prompt_text
                    logger.info(f"Found matching prompt using flexible matching: '{key}' with content: '{prompt_preview}'")
                    # Print full prompt for testing
                    print(f"here is the full prompt used for flexible matching with key '{key}': {system_prompt_text}")
                    break

            if not system_prompt_text:
                logger.error(f"No system prompt found for section '{section}' after trying all matching methods.")
                return f"Error: Not enough information is provided. No system prompt found for section '{section}'."

        # Add system prompt to batch
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

        # Get Gemini model
        model = model_loader.get_model("gemini", "gemini-2.5-flash-preview-04-17")

        try:
            response = model.predict(contents, max_retries=max_retries, base_retry_delay=base_retry_delay)
            return response
        except APIRateLimitError:
            return "Error: Rate limit exceeded after maximum retries."
        except APIError as e:
            error_str = str(e)
            if "Unable to determine the intended type of the `dict`" in error_str:
                # Handle format error
                logger.error(f"Format error in batch: {error_str}")
                # Try to fix the batch format and retry
                try:
                    fixed_contents = []
                    for item in contents:
                        fixed_contents.append({"text": str(item) if not isinstance(item, dict) or 'text' not in item else item['text']})
                    logger.info("Attempted to fix batch format, retrying...")
                    response = model.predict(fixed_contents, max_retries=max_retries, base_retry_delay=base_retry_delay)
                    return response
                except Exception as retry_e:
                    return f"Error: Failed to fix format and retry: {str(retry_e)}"
            return f"Error: {error_str}"
        except Exception as e:
            logger.error(f"Gemini query error: {str(e)}")
            return f"Error: Gemini query failed: {str(e)}"

    async def get_base64_images_for_section(self, section: str) -> List[Dict[str, Any]]:
        """
        Fetches images for a given case_id and section from MongoDB,
        downloads them from their Azure URL, and returns them as base64 encoded strings.

        Args:
            section: The section to get images for.

        Returns:
            A list of dictionaries, each containing a base64-encoded image.
        """
        logger.info(f"Fetching images for case '{self.case_id}', section '{section}'")
        base64_images = []

        try:
            # Get the case data
            case_data = self.case_repo.get_by_case_id(self.case_id)
            if not case_data:
                logger.error(f"Case '{self.case_id}' not found")
                return []

            all_images = case_data.get("images", [])

            # Filter images by the requested section
            section_images = [img for img in all_images if img.get("section") == section]

            if not section_images:
                logger.info(f"No images found for case '{self.case_id}', section '{section}'")
                return []

            for image_meta in section_images:
                azure_url = image_meta.get("azure_url")
                description = image_meta.get("description", "No description")
                file_path = image_meta.get("file_path", "No path")

                if not azure_url:
                    logger.warning(f"Skipping image (no azure_url): {description} in case '{self.case_id}'")
                    continue

                try:
                    # Fetch the image from Azure URL
                    response = requests.get(azure_url, stream=True, timeout=20)
                    response.raise_for_status()

                    # Read image content
                    image_bytes = response.content

                    if not image_bytes:
                        logger.warning(f"Skipping image (empty content): {description} from {azure_url}")
                        continue

                    # Encode image bytes to base64
                    base64_encoded_image = base64.b64encode(image_bytes).decode('utf-8')

                    # Determine content type
                    file_extension = os.path.splitext(file_path)[1].lower()
                    content_type = f"image/{file_extension.replace('.', '')}"
                    if 'png' in file_extension:
                        content_type = 'image/png'
                    elif 'jpg' in file_extension or 'jpeg' in file_extension:
                        content_type = 'image/jpeg'
                    elif 'gif' in file_extension:
                        content_type = 'image/gif'

                    # Prepend the data URI scheme header
                    base64_data_uri = f"data:{content_type};base64,{base64_encoded_image}"

                    base64_images.append({
                        "description": description,
                        "file_path": file_path,
                        "section": section,
                        "base64_content": base64_data_uri
                    })

                    logger.info(f"Successfully fetched and encoded image: {description} from {azure_url}")

                except requests.exceptions.RequestException as req_err:
                    logger.error(f"Error fetching image {description} from {azure_url}: {req_err}")
                except Exception as enc_err:
                    logger.error(f"Error encoding image {description} from {azure_url}: {enc_err}")

        except Exception as e:
            logger.error(f"Error retrieving or processing images for case '{self.case_id}', section '{section}': {e}")
            import traceback
            logger.error(traceback.format_exc())

        logger.info(f"Finished fetching images for case '{self.case_id}', section '{section}'. Found {len(base64_images)} images.")
        return base64_images

    async def get_all_exhibits(self) -> tuple:
        """
        Fetches all exhibits (images and PDFs) for a given case_id,
        downloads them from their Azure URL, and returns them as base64 encoded strings.
        For PDFs, each page is converted to an image.

        Returns:
            A tuple containing:
            - A list of dictionaries, each containing a base64-encoded image
            - A list of exhibit names
        """
        logger.info(f"Fetching all exhibits for case '{self.case_id}'")
        base64_images = []
        exhibit_names = []  # List to store exhibit names

        try:
            # Get the case data
            case_data = self.case_repo.get_by_case_id(self.case_id)
            if not case_data:
                logger.error(f"Case '{self.case_id}' not found")
                return [], []

            # Check if exhibits exist
            if "exhibits" not in case_data or not case_data["exhibits"]:
                logger.info(f"No exhibits found for case '{self.case_id}'")
                return [], []

            exhibits = case_data["exhibits"]
            exhibit_count = 1  # Counter for exhibit numbering

            # Process exhibit images
            exhibit_images = exhibits.get("images", [])
            for image_meta in exhibit_images:
                azure_url = image_meta.get("azure_url")
                description = image_meta.get("description", f"Exhibit {exhibit_count}")
                file_path = image_meta.get("file_path", "No path")

                if not azure_url:
                    logger.warning(f"Skipping exhibit image (no azure_url): {description} in case '{self.case_id}'")
                    continue

                try:
                    # Fetch the image from Azure URL
                    response = requests.get(azure_url, stream=True, timeout=20)
                    response.raise_for_status()

                    # Read image content
                    image_bytes = response.content

                    if not image_bytes:
                        logger.warning(f"Skipping exhibit image (empty content): {description} from {azure_url}")
                        continue

                    # Encode image bytes to base64
                    base64_encoded_image = base64.b64encode(image_bytes).decode('utf-8')

                    # Determine content type
                    file_extension = os.path.splitext(file_path)[1].lower()
                    content_type = f"image/{file_extension.replace('.', '')}"
                    if 'png' in file_extension:
                        content_type = 'image/png'
                    elif 'jpg' in file_extension or 'jpeg' in file_extension:
                        content_type = 'image/jpeg'
                    elif 'gif' in file_extension:
                        content_type = 'image/gif'

                    # Prepend the data URI scheme header
                    base64_data_uri = f"data:{content_type};base64,{base64_encoded_image}"

                    # Add to the list with exhibit number
                    # Check if description already contains "Exhibit" to avoid duplication
                    if "Exhibit" in description:
                        # Use the description as is
                        image_description = description
                    else:
                        # Add "Exhibit" prefix
                        image_description = f"Exhibit {exhibit_count}: {description}"

                    # Add the exhibit name to the list (without page numbers)
                    # Extract the base name without page numbers like (1/3)
                    base_name = image_description
                    if " (" in base_name and ")" in base_name:
                        base_name = base_name.split(" (")[0]

                    # Only add if not already in the list
                    if base_name not in exhibit_names:
                        exhibit_names.append(base_name)

                    base64_images.append({
                        "description": image_description,
                        "file_path": file_path,
                        "section": "Exhibits",
                        "base64_content": base64_data_uri,
                        "exhibit_number": exhibit_count
                    })

                    logger.info(f"Successfully fetched and encoded exhibit image: {description} from {azure_url}")
                    exhibit_count += 1

                except Exception as e:
                    logger.error(f"Error processing exhibit image {description} from {azure_url}: {e}")

            # Process exhibit PDFs
            exhibit_pdfs = exhibits.get("pdfs", [])
            for pdf_meta in exhibit_pdfs:
                azure_url = pdf_meta.get("azure_url")
                description = pdf_meta.get("description", f"Exhibit {exhibit_count}")

                if not azure_url:
                    logger.warning(f"Skipping exhibit PDF (no azure_url): {description} in case '{self.case_id}'")
                    continue

                try:
                    # Convert PDF to images
                    pdf_images = await convert_pdf_to_images(azure_url, description)

                    # Add exhibit number to each page
                    for img in pdf_images:
                        img["exhibit_number"] = exhibit_count

                    # Add the exhibit name to the list (only once per PDF)
                    if pdf_images:
                        # Check if description already contains "Exhibit" to avoid duplication
                        if "Exhibit" in description:
                            # Use the description as is
                            pdf_description = description
                        else:
                            # Add "Exhibit" prefix
                            pdf_description = f"Exhibit {exhibit_count}: {description}"

                        # Extract the base name without page numbers or other indicators
                        base_name = pdf_description
                        if " (" in base_name and ")" in base_name:
                            base_name = base_name.split(" (")[0]

                        # Only add if not already in the list
                        if base_name not in exhibit_names:
                            exhibit_names.append(base_name)

                    # Add all pages to the result
                    base64_images.extend(pdf_images)

                    # Increment exhibit counter only once per PDF
                    if pdf_images:
                        exhibit_count += 1

                except Exception as e:
                    logger.error(f"Error processing exhibit PDF {description} from {azure_url}: {e}")

            # Sort by exhibit number
            base64_images.sort(key=lambda x: (x.get("exhibit_number", 999), x.get("page_number", 0)))

        except Exception as e:
            logger.error(f"Error retrieving or processing exhibits for case '{self.case_id}': {e}")
            import traceback
            logger.error(traceback.format_exc())

        logger.info(f"Finished fetching exhibits for case '{self.case_id}'. Found {len(base64_images)} exhibit images and {len(exhibit_names)} exhibit names.")
        return base64_images, exhibit_names

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

    def __del__(self):
        """
        Ensure cleanup when the object is garbage collected.
        """
        self.cleanup()
