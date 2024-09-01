from setuptools import setup, find_packages

setup(
    name="oculizer",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        # List your dependencies here
        'numpy',
        'scipy',
        'sounddevice',
        'librosa',
        'pydub',
        'scipy', 
        'sounddevice',
        'soundfile',
        'sklearn',
        'PyDMXControl'
    ],
)