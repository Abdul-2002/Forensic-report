"""
Case repository for database operations.
"""
from typing import Dict, Any, List, Optional

from src.core.config import CASE_COLLECTION
from src.core.logging_config import get_logger
from src.db.models.case import Case
from src.db.repositories.base_repository import BaseRepository

logger = get_logger(__name__)

def get_case_repository():
    """
    Get the case repository.

    Returns:
        The case repository.
    """
    return CaseRepository()

class CaseRepository(BaseRepository[Case]):
    """
    Case repository for database operations.
    """

    def __init__(self):
        """
        Initialize the case repository.
        """
        super().__init__(CASE_COLLECTION, Case)

    def get_by_case_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a case by case ID.

        Args:
            case_id: The case ID to search for.

        Returns:
            The case document or None if not found.
        """
        return self.read_one({"case_id": case_id})

    def get_all_cases(self) -> List[Dict[str, Any]]:
        """
        Get all cases.

        Returns:
            A list of all case documents.
        """
        cases = self.read({})

        # Sort cases by created_at or date
        cases.sort(key=lambda x: (
            x.get("created_at", ""),
            x.get("date", "")
        ), reverse=True)

        return cases

    def add_image_to_case(self, case_id: str, image_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add an image to a case.

        Args:
            case_id: The case ID.
            image_metadata: The image metadata.

        Returns:
            A dictionary with the number of modified documents or an error message.
        """
        return self.update(
            {"case_id": case_id},
            {"$push": {"images": image_metadata}}
        )

    def add_pdf_to_case(self, case_id: str, pdf_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a PDF to a case.

        Args:
            case_id: The case ID.
            pdf_metadata: The PDF metadata.

        Returns:
            A dictionary with the number of modified documents or an error message.
        """
        return self.update(
            {"case_id": case_id},
            {"$push": {"pdf": pdf_metadata}}
        )

    def add_exhibit_to_case(self, case_id: str, exhibit_type: str, exhibit_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add an exhibit to a case.

        Args:
            case_id: The case ID.
            exhibit_type: The exhibit type (images or pdfs).
            exhibit_metadata: The exhibit metadata.

        Returns:
            A dictionary with the number of modified documents or an error message.
        """
        return self.update(
            {"case_id": case_id},
            {"$push": {f"exhibits.{exhibit_type}": exhibit_metadata}}
        )

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find a single document in the collection.

        Args:
            query: The query to filter documents.

        Returns:
            The document or None if not found.
        """
        return self.read_one(query)

    def find_all(self) -> List[Dict[str, Any]]:
        """
        Find all documents in the collection.

        Returns:
            A list of all documents.
        """
        return self.get_all_cases()

    def delete_one(self, query: Dict[str, Any]) -> bool:
        """
        Delete a single document from the collection.

        Args:
            query: The query to filter documents.

        Returns:
            True if a document was deleted, False otherwise.
        """
        result = self.delete(query)
        return result.get("deleted_count", 0) > 0
