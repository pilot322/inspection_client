import sys
from cx_Freeze import setup, Executable

import site
site.addsitedir(sys.prefix + "/Lib/site-packages")

includes= ['setuptools']

# Include your files and folders
includefiles = ['pages/',
                'components/',
                'resources/',
                r'C:\Users\micha\Folder\Work\inspection_client\env\Lib\site-packages\PyQt5\Qt5\plugins\platforms'
]

# Exclude unnecessary packages
excludes = ['cx_Freeze','pydoc_data']

# Dependencies are automatically detected, but some modules need help.
packages = ['tensorflow', 'sklearn', 'skimage', 'scipy', 'numpy', 'cv2', 'matplotlib', 'mplcursors', 'dotenv', 'PyQt5']    

base = None
shortcutName = None
shortcutDir = None
if sys.platform == "win32":
    base = "Win32GUI"
    shortcutName='Inspection Client'
    shortcutDir="DesktopFolder"

setup(
    name = 'Inspection Client',
    version = '0.8.5',
    description = '-',
    author = 'michalis lappas',
    author_email = '',
    options = {'build_exe': {
        'includes': includes,
        'excludes': excludes,
        'packages': packages,
        'include_files': includefiles,
        'include_msvcr': True
        }
        }, 
    executables = [Executable('main.py', 
    base = 'Console', # "Console", base, # None
    #icon='images/icon.ico', 
    shortcut_name = shortcutName, 
    shortcut_dir = shortcutDir)]
)