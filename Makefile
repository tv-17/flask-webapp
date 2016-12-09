.PHONY: all clean env package run create_stack
all: clean package

export GIT_COMMIT=$(shell git log -n 1 --pretty=format:"%H")

clean:
	- rm -rf env
	- rm *.pyc

env: clean
	virtualenv env
	. env/bin/activate && pip install pip --upgrade
	. env/bin/activate && pip install setuptools --upgrade
	. env/bin/activate && pip install -r requirements.txt

package: env
	mkdir BUILD
	cp -r app BUILD
	cp requirements.txt BUILD
	cd BUILD; zip -r -X webapp-$$GIT_COMMIT.zip .
	mv BUILD/webapp-$$GIT_COMMIT.zip .
	rm -rf BUILD/

upload: package
	. env/bin/activate && aws s3 cp webapp-$$GIT_COMMIT.zip s3://thivan-sample-data --profile "profile cr-training1" --region us-east-1
	rm webapp-$$GIT_COMMIT.zip

create_stack: upload
	python cloudformation/troposphere/webapp.py > cloudformation/json/webapp.json
	. env/bin/activate && aws cloudformation create-stack --stack-name webapp-stack \
	--template-body file:////Users/thivanvisvanathan/clearscore/cloudformation/json/webapp.json \
	--parameters ParameterKey=WebappZip,ParameterValue=webapp-$$GIT_COMMIT.zip \
	--profile "profile cr-training1" \
	--region us-east-1

update_stack: upload
	python cloudformation/troposphere/webapp.py > cloudformation/json/webapp.json
	. env/bin/activate && aws cloudformation update-stack --stack-name webapp-stack \
	--template-body file:////Users/thivanvisvanathan/clearscore/cloudformation/json/webapp.json \
	--parameters ParameterKey=WebappZip,ParameterValue=webapp-$$GIT_COMMIT.zip \
	--profile "profile cr-training1" \
	--region us-east-1

delete_stack:
	python cloudformation/troposphere/webapp.py > cloudformation/json/webapp.json
	. env/bin/activate && aws cloudformation delete-stack --stack-name webapp-stack \
	--profile "profile cr-training1" \
	--region us-east-1

run:
	. env/bin/activate && \
	export FLASK_APP=app/app.py && \
	export FLASK_DEBUG=1 && \
	flask run
