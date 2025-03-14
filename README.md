# Anti-immigrant sentiment

_Version 0.1.0_

We measure anti-immigrant sentiment in Germany expressed in online reviews of immigrant establishments before and after the large-scale refugee influx in 2015.

## Current status

__Tripadvisor (restaurants)__:
- [x] Scraper written
- [x] Scraper testing: 4/4 municipalities scraped
- [ ] Scraper running

__Google Maps (restaurants, places of worship, grocery stores)__:
- [ ] Scraper written
- [ ] Scraper testing:
- [ ] Scraper running:

## Project organization

```
.
├── .gitignore
├── environment.yml
├── LICENSE.md
├── Makefile
├── README.md
├── data               <- All project data, ignored by git
│   ├── processed      <- Final data sets for modeling. (PG)
│   ├── raw            <- The original, immutable data dump (RO)
│   └── temp           <- Intermediate, transformed data (PG)
├── docs               <- Documentation
│   ├── manuscript     <- Manuscript source (HW)
│   └── reports        <- Other project reports and notebooks (HW)
├── results
│   ├── figures        <- Figures for the manuscript or reports (PG)
│   ├── misc           <- Other output (PG)
│   └── tables         <- Tables (PG)
└── src                <- Source code (HW)
    └── external       <- External source code used (RO)

```
*RO* = read-only, *HW* = human-writeable, *PG* = project-generated. Repository organization implemented with [cookiecutter](https://github.com/cookiecutter/cookiecutter) using an adapted version of the [good-enough-project template](https://github.com/bvreede/good-enough-project) by Barbara Vreede. The fork is available [here](https://github.com/maximilian-sprengholz/good-enough-project).

## Usage

To replicate the analysis and docs, you need to have [Anaconda](https://www.anaconda.com/products/individual) installed and `conda` available via shell. Dependencies which are unavailable for ARM-based Macs in the conda/pip repositories (e.g. Firefox) need to be manually installed (and potentially made available to PATH).

```bash
# create and activate conda environment (initialized as subdirectory ./env)
cd /path/to/anti-immigrant-sentiment
conda env create --prefix ./env --file environment.yml
conda activate ./env
# check if environment is active and python is in it
make checksetup
# start crawler
#make scrape_tripadvisor
#make scrape_googlemaps
# run analysis and make docs
#make all
```

## License

This project is licensed under the terms of the [MIT License](/LICENSE.md)