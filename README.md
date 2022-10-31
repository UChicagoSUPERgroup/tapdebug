Helping End-users Debug Their Trigger-Action Programs
===
# Introduction
This repository is a fullstack web-application that helps end-users debug their trigger-action programs in smart homes.
It is excuted as serveral docker containers - postgres, backend, frontend and nginx. 
## Postgres
The postgres container maintains a PostgresSQL database to support the system. User information, trigger-action program
 information, users' traces, etc. are stored in the database. 
## Backend 
The backend container runs a Django server that provides a varieties of APIs for the frontend. It provides APIs that 
log-in a user, APIs that fetch TAP rules, APIs that provide TAP patches, etc. The main algorithms for this project are 
executed in the backend.
## Frontend
The frontend container runs Angular as a frontend server. When users access our website through a browser, the frontend 
server send a copy of the website to the brower. Visual designs of the interface are done in the frontend code.
## Nginx
The nginx container runs a service listening on the machine's 80 and 443 port. It forwards requests from end-users to the 
correct target destinations (i.e. web request to frontend, API calls to backend).

You can build the fullstack web-application through docker-compose with our pre-written scripts.

# Pre-requisites
TapDebug runs as a fullstack web-application on a Linux server. To connect it with a Home I/O simulator, it has to be accessible
on a url (e.g. my.example.url) from the Windows machine running the simulator.

You need to install docker, docker-compose and git-lhs on the server.
 - [Setting up docker](https://docs.docker.com/engine/install/)
 - [Setting up docker-compose](https://docs.docker.com/compose/install/)

TapDebug does not support Windows or Windows Subsystem Linux. We tested it on native Ubuntu 18.04 and 20.04.

# Download TapDebug
```console
git clone git@github.com:UChicagoSUPERgroup/tapdebug.git
cd tapdebug
```

# Configure the server url
Modify the "host_domain" field in settings.json into your server's url (e.g. my.example.url).

# Build/run TapDebug
To initialize TapDebug (1st execution), run:
```console
./start_server_dev.sh --data data/homeio.sql
```
This will build all our images and run the containers. It will start a local web-application at port 80. If you wish to run the server 
on a different url from "localhost", please modify the url in settings.json. 
**Warning**: This sql contains admin name/password. To use TapDebug under production, please update them to avoid being attacked.

To run TapDebug without initialization (keeping the data), run:
```console
./start_server_dev.sh
```

# Create a user
On a separate terminal on the server, under the tapdebug folder, run:
```console
docker-compose exec -it backend python3 manage.py createusers -m [interface] [usercode]
```
This will create a user with "usercode" who will be able to access the interface specified.

Options for \[interface\] include:
 - "c": Control interface where users manually manage trigger-action programs.
 - "nf": Explicit-Feedback interface where users can provide explicit behavioral feedback to modify TAP rules.
 - "nn": Implicit-Feedback interface where the system learns to modify TAP rules from traces.

# Connect a Home I/O simulator
Now please refer to [TapDebug Home I/O Connector](https://github.com/UChicagoSUPERgroup/tapdebug-homeio-connector) 
for more details running Home I/O.

# Test our interface
Visit the following url to access the interface:
my.example.url/\[usercode\]/survey/\[taskid\].

Options for "taskid" are 6, 1, 3, 4, 5 and 12, representing 
task 0-5 in our paper. In these task pages, we have set up the TAP rules we used in our study.
