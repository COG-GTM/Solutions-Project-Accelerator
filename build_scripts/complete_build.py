import PyInstaller.__main__
import os

# Build executable 
PyInstaller.__main__.run([
    'runme.py',
    '--noconfirm', # Replace output directory without asking for confirmation
    '--onedir', # Create a one-folder bundle containing an executable
    '--windowed', # Do not provide a console window for standard i/o
    '--icon=./bin/logo.ico', # Apply that icon to a Windows executable
    '--version-file=file_version_info.txt', # Windows version details 
    '--log-level=INFO', # Amount of detail in build-time console messages. 
    '--add-data=./bin/logo.ico;./bin', # Additional non-binary files or folders to be added to the executable.
    '--add-data=./cairosvg/VERSION;./cairosvg', # Additional library folders 
    '--distpath=./build/dist', # Where to put the bundled app
    '--hidden-import=sqlalchemy.sql.default_comparator', # Hiidden import required
    '--hidden-import=cairosvg', # Additional hidden import library 
    '--workpath=./build' # Where to put all the temporary work files
])

# Create setup file
os.system('iscc '+os.getcwd()+'\\package_installer.iss')