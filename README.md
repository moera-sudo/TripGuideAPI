# TripGuideAPI

To install the project:

``` python
pip install -r requirements.txt
```

Then create your .env file with the following variables:

``` python 
#Application settings

APP_NAME=your_app_name

DEBUG=true

APP_VERSION=your_version

APP_DESCRIPTION=your_description

  

#Database settings

DB_USERNAME=your_pg_name

DB_PASSWORD=your_pg_password

DB_HOST=localhost

DB_PORT=5432

DB_NAME=your_db_name

DB_DRIVER=asyncpg

  

#JWT Settings

SECRET_KEY=your_secret_key

REFRESH_SECRET_KEY=your_second_secret_key

ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=30

REFRESH_TOKEN_EXPIRE_DAYS=7

  

#Email Settings

MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_FROM=
MAIL_PORT=
MAIL_SERVER=
MAIL_FROM_NAME=
MAIL_STARTTLS=
MAIL_SSL_TLS=
USE_CREDENTIALS=
VALIDATE_CERTS=
TEMPLATE_FOLDER=templates

#Verification code settings
VERIFICATION_CODE_EXPIRE_MINUTES=15
```



To start project use:
```
uvicorn main:app --reload --port 8000
```
