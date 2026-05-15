# backend/sideview/model.py
"""
Sideview Model Wrapper
Provides a model interface compatible with the existing drone_router.py
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Global model instance
_model_instance: Optional['SideViewModel'] = None


class SideViewModel:
    """
    Wrapper class for the sideview transfer learning model.
    Provides compatibility with existing drone router code.
    """
    
    def __init__(self):
        """Initialize the sideview model."""
        self.model = None
        self.model_path = Path(__file__).parent / "plant_disease_transfer_model.h5"
        self.labels_path = Path(__file__).parent / "labels.json"
        self._load_model()
    
    def _load_model(self):
        """Load the transfer model if available."""
        try:
            from sideview.test_transfer_model import TransferModelPredictor
            
            if self.model_path.exists() and self.labels_path.exists():
                self.model = TransferModelPredictor(
                    model_path=str(self.model_path),
                    labels_path=str(self.labels_path)
                )
                logger.info("Sideview model loaded successfully")
            else:
                logger.warning(f"Model files not found at {self.model_path}")
                self.model = None
        except Exception as e:
            logger.error(f"Failed to load sideview model: {e}")
            self.model = None
    
    def predict(self, image_path: str):
        """
        Predict disease from image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Prediction results dictionary
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")
        
        return self.model.predict(image_path)
    
    @classmethod
    def get_instance(cls) -> 'SideViewModel':
        """Get or create singleton instance."""
        global _model_instance
        if _model_instance is None:
            _model_instance = cls()
        return _model_instance
