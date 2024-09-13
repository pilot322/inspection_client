from cx_Freeze import Executable, setup as cx_setup
import os
import sys
import site

site.addsitedir(sys.prefix + "/Lib/site-packages")

includes = [
    'setuptools', 
    'tensorflow', 
    'keras', 
    'keras.api', 
    'keras.api.models', 
    'keras.api.preprocessing', 
    'keras.api.preprocessing.image'
]

# Specify only necessary files and directories to include
includefiles = [
    'pages/',  # Assuming this directory doesn't contain .py files you want to exclude
    'components/',  # Same assumption as above
    'resources/',  # Only include the compiled .pyd files
    r'C:\Users\Mixalis\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.10_qbz5n2kfra8p0\LocalCache\local-packages\Python310\site-packages\PyQt5\Qt5\plugins\platforms'
]

# Explicitly include only the compiled .pyd files

compiled_includefiles = []

for file in os.listdir(os.path.join(os.getcwd(), 'resources')):
    if file.endswith('.pyd'):
        compiled_includefiles.append( (os.path.join('resources', file), os.path.join('resources', file)) )


# Combine the include files
includefiles += compiled_includefiles

excludes = ['cx_Freeze', 'pydoc_data']

packages = [
    'sklearn', 
    'skimage', 
    'scipy', 
    'numpy', 
    'cv2', 
    'matplotlib', 
    'mplcursors', 
    'dotenv', 
    'PyQt5',
    'resources'
]

base = None
shortcutName = None
shortcutDir = None
if sys.platform == "win32":
    base = "Win32GUI"
    shortcutName = 'Inspection Client'
    shortcutDir = "DesktopFolder"

cx_setup(
    name='Inspection Client',
    version='0.8.5',
    description='-',
    author='michalis lappas',
    author_email='',
    options={
        'build_exe': {
            'includes': includes,
            'excludes': excludes,
            'packages': packages,
            'include_files': includefiles,
            'include_msvcr': True
        }
    }, 
    executables=[Executable(
        'main.py', 
        base='Console',
        shortcut_name=shortcutName, 
        shortcut_dir=shortcutDir
    )]
)
