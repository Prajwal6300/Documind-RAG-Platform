"""Auto-executed at Python interpreter startup when run from this directory.

Limits BLAS/OMP/OpenBLAS threading so NumPy, SciPy, scikit-learn and
sentence-transformers do not spawn excessive threads on memory-constrained
Windows machines. Must run BEFORE numpy/scipy are imported.
"""

import os

_THREADING_VARS = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)

for _var in _THREADING_VARS:
    os.environ.setdefault(_var, "1")