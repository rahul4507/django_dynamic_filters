from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="django-dynamic-filters",
    version="0.1.0",
    author="Rahul Hiragond",
    author_email="rahulhiragond04@gmail.com",
    description="Dynamic filtering capabilities for Django models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/django-dynamic-filters",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
    install_requires=[
        "Django>=3.2",
    ],
)