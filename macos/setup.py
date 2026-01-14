"""py2app setup script for Weather Trader macOS application."""
import sys
from pathlib import Path
from setuptools import setup

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

APP = ['launcher.py']

DATA_FILES = [
    ('frontend', [
        'frontend/dist/index.html',
        'frontend/dist/assets',
    ]),
    ('resources', [
        'macos/resources/icon.icns',
    ]),
]

OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'CFBundleName': 'WeatherTrader',
        'CFBundleDisplayName': 'Weather Trader',
        'CFBundleIdentifier': 'com.weathertrader.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSMinimumSystemVersion': '12.0',
        'LSUIElement': False,
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'CFBundleIconFile': 'icon.icns',
        'NSHumanReadableCopyright': 'Copyright 2026',
    },
    'packages': [
        'fastapi',
        'uvicorn',
        'httpx',
        'sqlalchemy',
        'aiosqlite',
        'pydantic',
        'pydantic_settings',
        'rumps',
        'requests',
        'schedule',
    ],
    'includes': [
        'app',
        'data',
        'execution',
        'utils',
    ],
    'excludes': [
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
    ],
    'iconfile': 'macos/resources/icon.icns',
    'resources': [
        'frontend/dist',
    ],
}

setup(
    name='WeatherTrader',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
