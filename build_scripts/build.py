import PyInstaller.__main__
import site

site_package_path = site.getsitepackages()[1]
user_site_packages = site.getusersitepackages()

PyInstaller.__main__.run([
    'runme.py',
    '--noconfirm', # Replace output directory without asking for confirmation
    '--onedir', # Create a one-folder bundle containing an executable
    '--console', # Do not provide a console window for standard i/o
    '--icon=./bin/logo.ico', # Apply that icon to a Windows executable
    '--version-file=file_version_info.txt',# Windows version details 
    '--log-level=INFO', # Amount of detail in build-time console messages.
    '--collect-data=paddle', # required for paddleocr
    '--collect-data=scipy', # required for paddleocr
    '--collect-all=paddleocr', # required for paddleocr
    '--collect-all=lmdb', # required for paddleocr
    '--add-data=./bin/logo.ico;./bin', # Additional non-binary files or folders to be added to the executable.
    '--add-data=./cairosvg/VERSION;./cairosvg', # Additional library folders 
    '--add-data='+site_package_path+'/Shapely.libs;./Shapely.libs', # Additional library folders 
    '--add-data='+site_package_path+'/cairocffi;./cairocffi', # Additional library folders 
    '--add-data=./Paddle-OCR;./Paddle-OCR', # Opitcal Character Recognition models
    '--add-data=./Potrace;./Potrace', # SVG Simplification
    '--additional-hooks-dir=. hook_paddle.py',
    '--additional-hooks-dir=. hook_paddleocr.py',
    '--distpath=./build/dist', # Where to put the bundled app
    '--hidden-import=imghdr',
    '--hidden-import=imgaug',
    '--hidden-import=pyclipper',
    '--hidden-import=sqlalchemy.sql.default_comparator', # Hiidden import required
    '--hidden-import=cairosvg', # Additional hidden import library 
    '--workpath=./build' # Where to put all the temporary work files
    ])