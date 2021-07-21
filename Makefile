.PHONY: checksetup analysis docs

checksetup:
	conda info --envs \
	&& echo $$(which python)

analysis:

docs:

all: analysis docs
