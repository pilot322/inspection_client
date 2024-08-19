@echo off
REM Step a: Call compile.py to compile the specified .py files with Cython
echo Compiling with Cython...
python compile.py build_ext --inplace
if %ERRORLEVEL% neq 0 (
    echo Failed to compile with Cython.
    exit /b %ERRORLEVEL%
)

REM Step b: Move svm.py, utils.py, and features.py from the resources directory to the protected_resources directory
echo Moving .py files to protected_resources...
move /Y resources\svm.py protected_resources\svm.py
move /Y resources\utils.py protected_resources\utils.py
move /Y resources\features.py protected_resources\features.py

REM Step c: Call setup.py to build the executable with cx_Freeze
echo Building with cx_Freeze...
python setup.py build
if %ERRORLEVEL% neq 0 (
    echo Failed to build with cx_Freeze.
    REM Move the files back if the build fails
    echo Moving .py files back to resources directory...
    move /Y protected_resources\svm.py resources\svm.py
    move /Y protected_resources\utils.py resources\utils.py
    move /Y protected_resources\features.py resources\features.py
    exit /b %ERRORLEVEL%
)

REM Step d: Move the files back to the resources directory
echo Moving .py files back to resources directory...
move /Y protected_resources\svm.py resources\svm.py
move /Y protected_resources\utils.py resources\utils.py
move /Y protected_resources\features.py resources\features.py

echo Build process completed successfully!
