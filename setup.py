from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="moodle-downloader",
    version="1.0.0",
    author="Tomer Bar",
    author_email="tomerbar2021@gmail.com",
    description="Automated Moodle course material downloader",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tomerbar201/moodle-downloader",
    packages=find_packages(include=['src', 'src.*']),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "moodledown-gui=run_gui:main",
            "moodledown-cli=run_cli:main",
        ],
    },
)
