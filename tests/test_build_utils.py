import pytest
import shutil
from unittest.mock import patch, MagicMock
from src.build import clean_build

def test_clean_build_success():
    """Test standard clean build success where rmtree works immediately."""
    with patch('os.path.exists', return_value=True) as mock_exists, \
         patch('shutil.rmtree') as mock_rmtree:
        
        clean_build()
        
        # Should attempt to remove 'build' and 'dist'
        # Can't be sure of exact count if spec file check exists etc.
        # But should allow no exception.
        assert mock_rmtree.call_count >= 2

def test_clean_build_retry_success():
    """Test that it retries on OSError and eventually succeeds."""
    with patch('os.path.exists', return_value=True), \
         patch('shutil.rmtree') as mock_rmtree, \
         patch('time.sleep') as mock_sleep:
         
        # Simulate: 
        # 1. 'build': Fail, Fail, Success
        # 2. 'dist': Success
        
        # Side effects must yield result or raise exception
        mock_rmtree.side_effect = [OSError("Locked"), OSError("Locked"), None, None]
        
        clean_build()
        
        # Total calls: 3 for 'build' (2 fails + 1 success), 1 for 'dist' (success) = 4
        # Assuming list iteration order is exactly [build, dist]
        assert mock_rmtree.call_count == 4

def test_clean_build_fail_max_retries():
    """Test that it raises exception after max retries."""
    with patch('os.path.exists', return_value=True), \
         patch('shutil.rmtree') as mock_rmtree, \
         patch('time.sleep'):
         
        mock_rmtree.side_effect = OSError("Locked forever")
        
        with pytest.raises(OSError):
            clean_build()
