import os
import PyInstaller.__main__
import site
import shutil

site_package_path = site.getsitepackages()[1]
user_site_packages = site.getusersitepackages()

PyInstaller.__main__.run([
    'runme.py',
    '--noconfirm', # Replace output directory without asking for confirmation
    '--onedir', # Create a one-folder bundle containing an executable
    '--windowed', # Do not provide a console window for standard i/o
    '--log-level=DEBUG', # Amount of detail in build-time console messages.
    '--icon=./bin/logo.ico', # Apply that icon to a Windows executable
    '--version-file=file_version_info.txt',# Windows version details 
    '--log-level=INFO', # Amount of detail in build-time console messages.
    '--collect-data=paddle', # required for paddleocr
    '--collect-data=scipy', # required for paddleocr
    '--collect-all=paddleocr', # required for paddleocr
    '--collect-all=lmdb', # required for paddleocr
    '--add-data=./bin/logo.ico;./bin', # Additional non-binary files or folders to be added to the executable.
    '--add-data=./cairosvg/VERSION;./cairosvg', # Additional library folders
    '--add-data='+site_package_path+'/Cython/Utility/StringTools.c;./Cython/Utility', # Additional library folders
    '--add-data='+site_package_path+'/Shapely.libs;./Shapely.libs', # Additional library folders
    '--add-data='+site_package_path+'/cairocffi;./cairocffi', # Additional library folders
    '--add-data=./Paddle-OCR;./Paddle-OCR', # Opitcal Character Recognition models
    '--add-data=./SAM2.1;./SAM2.1', # Opitcal Character Recognition
    '--add-data=./Potrace;./Potrace', # SVG Simplification
    '--add-data=TaskbarLib.tlb;.', # Taskbar Library
    '--additional-hooks-dir=./build_scripts',
    '--additional-hooks-dir=. hook_paddle.py',
    '--additional-hooks-dir=. hook_paddleocr.py',
    '--distpath=./build/dist', # Where to put the bundled app
    '--hidden-import=imghdr',
    '--hidden-import=cython', # Hidden import
    '--hidden-import=imgaug',
    '--hidden-import=pyclipper',
    '--hidden-import=sqlalchemy.sql.default_comparator', # Hiidden import required
    '--hidden-import=cairosvg', # Additional hidden import library 
    '--workpath=./build' # Where to put all the temporary work files
    ])

# Copy the TaskbarLib.tlb to the runme build folder 
taskbar_lib_source = './TaskbarLib.tlb'
taskbar_lib_destination = './build/dist/runme/TaskbarLib.tlb'

shutil.copy(taskbar_lib_source, taskbar_lib_destination)

# Create setup file
os.system('iscc '+os.getcwd()+'\\build_scripts\\package_installer.iss')


# Change the version number in the file_version_info.txt by incrementing the last digit by 1
version_file_path = 'file_version_info.txt'
with open(version_file_path, 'r') as file:
    lines = file.readlines()
for i in range(len(lines)):
    if 'FileVersion' in lines[i] or 'ProductVersion' in lines[i]:
        version_line = lines[i]
        start_index = version_line.find(', u\'') + 2
        end_index = version_line.find('\')', start_index)
        version_str = version_line[start_index:end_index]
        version_parts = version_str.split('.')
        version_parts[-1] = str(int(version_parts[-1]) + 1)
        new_version_str = '.'.join(version_parts)
        lines[i] = version_line[:start_index] + new_version_str + version_line[end_index:]
    elif 'filevers=' in lines[i] or 'prodvers=' in lines[i]:
        version_line = lines[i]
        start_index = version_line.find('(') + 1
        end_index = version_line.find(')', start_index)
        version_tuple = version_line[start_index:end_index]
        version_parts = version_tuple.split(', ')
        version_parts[-1] = str(int(version_parts[-1]) + 1)
        new_version_tuple = ', '.join(version_parts)
        lines[i] = version_line[:start_index] + new_version_tuple + version_line[end_index:]
with open(version_file_path, 'w') as file:
    file.writelines(lines)