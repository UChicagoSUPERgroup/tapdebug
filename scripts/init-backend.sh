#!/bin/sh

host="postgres"

until PGPASSWORD=$(cat /run/secrets/db_password) psql -h $host -U $(cat /run/secrets/db_username) -c '\q' ifttt; do
  >&2 echo "DB unavailable - sleeping"
  sleep 1
done

>&2 echo "DB up - execute"

if test "$MIGRATION" = "true"; then
  >&2 echo "Running backend's migrations"
  python3 manage.py makemigrations backend --no-input
  python3 manage.py makemigrations --no-input
  python3 manage.py migrate --no-input --fake-init
  python3 manage.py initadmin
fi

python3 manage.py createcachetable

python3 manage.py collectstatic --no-input
if test "$DEBUG" = "false"; then
  echo "backend is ready to be up in prod mode"
  exec python3 manage.py runserver 0.0.0.0:8000 --settings=iot-tap-backend.settings.prod
else
  echo "backend is ready to be up in debug mode"
  exec python3 manage.py runserver 0.0.0.0:8000 --settings=iot-tap-backend.settings.local
fi
