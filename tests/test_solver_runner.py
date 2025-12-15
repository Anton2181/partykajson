import pytest
import sys
from unittest.mock import MagicMock, patch

def test_matplotlib_setup_at_import_time():
    """
    Verify that importing step_04_run_solver triggers matplotlib configuration
    immediately, ensuring font cache building happens before any solving function is called.
    """
    # Clean sys.modules to force re-import logic
    modules_to_remove = [k for k in sys.modules if 'step_04_run_solver' in k or 'matplotlib' in k]
    for m in modules_to_remove:
        # Don't actually remove real matplotlib if possible, but we need to mock it to intercept calls
        # If we remove it, we need to ensure we can re-import our mock
        del sys.modules[m]

    mock_mpl = MagicMock()
    # Mock specific submodules if accessed directly
    mock_plt = MagicMock()
    mock_mpl.pyplot = mock_plt

    with patch.dict(sys.modules, {'matplotlib': mock_mpl, 'matplotlib.pyplot': mock_plt}):
        # We also need to mock src.solver.solver since step_04 imports it
        # and we don't want to run real solver initialization during import if any
        mock_solver_module = MagicMock()
        sys.modules['src.solver.solver'] = mock_solver_module
        
        import src.step_04_run_solver
        
        # Verify matplotlib.use('Agg') was called
        mock_mpl.use.assert_called_with('Agg')
