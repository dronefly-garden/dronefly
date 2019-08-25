import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="quaggagriff",
    version="0.1.4",
    author="Ben Armstrong",
    author_email="synrg@debian.org",
    description="A Discord bot for naturalists",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/synrg/quaggagriff",
    install_requires=[
        "appdirs >= 1.4.3, < 2",
        "ebird-api >= 3.0.4, < 4",
        "discord.py >= 1.2.3, < 2",
        "tzlocal >= 2.0.0, < 3",
    ],
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
