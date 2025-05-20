from pathlib import Path
from setuptools import setup, find_packages

# Read the contents of README.md
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Read requirements from requirements.txt
with open("requirements.txt", "r", encoding="utf-8") as f:
    install_requires = [
        line.strip() 
        for line in f 
        if line.strip() and not line.startswith("#") and not line.startswith("-")
    ]

setup(
    name="kwork-scraper",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A high-performance async web scraper for Kwork.ru",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/kwork-scraper",
    packages=find_packages(where=".", exclude=["tests", "tests.*"]),
    package_data={
        "": ["*.json", "*.txt", "*.yaml", "*.yml"],
    },
    include_package_data=True,
    install_requires=install_requires,
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    entry_points={
        "console_scripts": [
            "kwork-scraper=integrations.kwork_parser:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/yourusername/kwork-scraper/issues",
        "Source": "https://github.com/yourusername/kwork-scraper",
    },
)
