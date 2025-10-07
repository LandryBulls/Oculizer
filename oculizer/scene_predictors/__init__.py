import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Available predictor versions
AVAILABLE_VERSIONS = ['v1', 'v3']  # v2 doesn't have a predictor.py file

def get_predictor(version='v1'):
    """
    Get a ScenePredictor class for the specified version.
    
    Args:
        version: Version string (e.g., 'v1', 'v3')
        
    Returns:
        ScenePredictor: Class of the specified predictor version
        
    Raises:
        ValueError: If version is not available
        ImportError: If the predictor module cannot be imported
    """
    if version not in AVAILABLE_VERSIONS:
        raise ValueError(f"Predictor version '{version}' not available. Available versions: {AVAILABLE_VERSIONS}")
    
    try:
        # Dynamic import of the predictor module
        module_path = f"oculizer.scene_predictors.{version}.predictor"
        module = importlib.import_module(module_path)
        
        # Get the ScenePredictor class from the module
        ScenePredictor = getattr(module, 'ScenePredictor')
        
        logger.info(f"Loaded ScenePredictor from {module_path}")
        return ScenePredictor
        
    except ImportError as e:
        logger.error(f"Failed to import predictor version {version}: {e}")
        raise ImportError(f"Could not import predictor version '{version}': {e}")
    except AttributeError as e:
        logger.error(f"ScenePredictor class not found in {version}: {e}")
        raise ImportError(f"ScenePredictor class not found in version '{version}': {e}")

def list_available_versions():
    """List all available predictor versions."""
    return AVAILABLE_VERSIONS.copy()

# Backward compatibility - default to v1
from .v1.predictor import ScenePredictor