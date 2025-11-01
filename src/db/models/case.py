"""
Case model for the application.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.db.models.base import BaseModel

class MetaData:
    """
    Metadata for files in a case.
    """

    def __init__(self, **kwargs):
        """
        Initialize the metadata with the given attributes.

        Args:
            **kwargs: The metadata attributes.
        """
        self.description: str = kwargs.get("description", "")
        self.file_path: str = kwargs.get("file_path", "")
        self.azure_url: Optional[str] = kwargs.get("azure_url")
        self.section: Optional[str] = kwargs.get("section")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the metadata to a dictionary.

        Returns:
            A dictionary representation of the metadata.
        """
        result = {
            "description": self.description,
            "file_path": self.file_path
        }

        if self.azure_url:
            result["azure_url"] = self.azure_url

        if self.section:
            result["section"] = self.section

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetaData":
        """
        Create a metadata instance from a dictionary.

        Args:
            data: The dictionary containing the metadata.

        Returns:
            A metadata instance.
        """
        return cls(**data)

class Case(BaseModel):
    """
    Case model for the application.
    """

    def __init__(self, **kwargs):
        """
        Initialize the case model with the given attributes.

        Args:
            **kwargs: The case attributes.
        """
        super().__init__(**kwargs)
        self.case_id: str = kwargs.get("case_id", "")
        self.case_name: str = kwargs.get("case_name", "")
        self.location: str = kwargs.get("location", "")
        self.date: str = kwargs.get("date", "")
        self.time: str = kwargs.get("time", "")
        self.description: str = kwargs.get("description", "")

        # Convert images and pdf lists to MetaData objects if they are dictionaries
        images_data = kwargs.get("images", [])
        self.images: List[MetaData] = [
            MetaData.from_dict(img) if isinstance(img, dict) else img
            for img in images_data
        ]

        pdf_data = kwargs.get("pdf", [])
        self.pdf: List[MetaData] = [
            MetaData.from_dict(pdf) if isinstance(pdf, dict) else pdf
            for pdf in pdf_data
        ]

        self.embedding: str = kwargs.get("embedding", "")

        # Additional case details
        self.case_type: str = kwargs.get("case_type", "")
        self.inspection_date: Optional[str] = kwargs.get("inspection_date")
        self.inspector_name: Optional[str] = kwargs.get("inspector_name")
        self.hub_file_number: Optional[str] = kwargs.get("hub_file_number")
        self.injured_party_name: Optional[str] = kwargs.get("injured_party_name")
        self.property_name: Optional[str] = kwargs.get("property_name")
        self.property_address: Optional[str] = kwargs.get("property_address")
        self.incident_date: Optional[str] = kwargs.get("incident_date")
        self.incident_time: Optional[str] = kwargs.get("incident_time")
        self.injured_party_present: Optional[str] = kwargs.get("injured_party_present")
        self.voice_record_allowed: Optional[str] = kwargs.get("voice_record_allowed")
        self.voice_record_link: Optional[str] = kwargs.get("voice_record_link")
        self.dcof_test: Optional[str] = kwargs.get("dcof_test")
        self.dcof_explanation: Optional[str] = kwargs.get("dcof_explanation")
        self.handwritten_note: Optional[str] = kwargs.get("handwritten_note")
        self.note_text: Optional[str] = kwargs.get("note_text")
        self.client_location: Optional[str] = kwargs.get("client_location")

        # Exhibits
        exhibits_data = kwargs.get("exhibits", {})
        if exhibits_data:
            self.exhibits = {
                "images": [
                    MetaData.from_dict(img) if isinstance(img, dict) else img
                    for img in exhibits_data.get("images", [])
                ],
                "pdfs": [
                    MetaData.from_dict(pdf) if isinstance(pdf, dict) else pdf
                    for pdf in exhibits_data.get("pdfs", [])
                ]
            }
        else:
            self.exhibits = {"images": [], "pdfs": []}

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the case model to a dictionary.

        Returns:
            A dictionary representation of the case model.
        """
        result = super().to_dict()
        result.update({
            "case_id": self.case_id,
            "case_name": self.case_name,
            "location": self.location,
            "date": self.date,
            "time": self.time,
            "description": self.description,
            "images": [img.to_dict() if hasattr(img, 'to_dict') else img for img in self.images],
            "pdf": [pdf.to_dict() if hasattr(pdf, 'to_dict') else pdf for pdf in self.pdf],
            "embedding": self.embedding,
            "case_type": self.case_type,
            "exhibits": {
                "images": [img.to_dict() if hasattr(img, 'to_dict') else img for img in self.exhibits["images"]],
                "pdfs": [pdf.to_dict() if hasattr(pdf, 'to_dict') else pdf for pdf in self.exhibits["pdfs"]]
            }
        })

        # Add optional fields if they exist
        optional_fields = [
            "inspection_date", "inspector_name", "hub_file_number", "injured_party_name",
            "property_name", "property_address", "incident_date", "incident_time",
            "injured_party_present", "voice_record_allowed", "voice_record_link",
            "dcof_test", "dcof_explanation", "handwritten_note", "note_text",
            "client_location"
        ]

        for field in optional_fields:
            value = getattr(self, field, None)
            if value is not None:
                result[field] = value

        return result
