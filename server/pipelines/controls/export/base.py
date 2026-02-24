"""Abstract base class for export templates."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict

from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession


class ExportTemplate(ABC):
    """Base class for all export templates.

    Subclasses must set TEMPLATE_NAME and implement query() + build_workbook().
    """

    TEMPLATE_NAME: str
    TEMPLATE_DESCRIPTION: str

    @abstractmethod
    async def query(self, db: AsyncSession, evaluation_date: datetime) -> List[Dict]:
        """Fetch rows from DB as-of evaluation_date."""

    @abstractmethod
    def build_workbook(self, rows: List[Dict], evaluation_date: datetime) -> Workbook:
        """Build openpyxl Workbook from queried rows."""
