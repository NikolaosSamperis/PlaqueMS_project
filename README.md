# PlaqueMS
## *An Integrative Web Platform for Atherosclerosis Omics Analysis.*
Facilitating Visual and Predictive Insights into Atherosclerotic Plaque Biology

## Prerequisites
Download and install:
- Python 3.11.9
- Django 5.1.7
- Django Rest Framework 3.15.2
- Cytoscape Desktop 3.10.3
- clusterMaker2 2.3.4
- Neo4j Desktop 1.6.1
- Neo4j DBMS 5.24.2
- MySQL Community Server 8.0.40
- (optional) A Python IDE; recommended: Visual Studio Code or Pycharm
- (optional) Git Bash for easier Unix-style command line use on Windows

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/NikolaosSamperis/PlaqueMS_project.git
cd PlaqueMS_project
```

### Project Structure

```
PlaqueMS_project/
├── login/                
├── protein/              
├── network/              
├── templates/            # HTML templates
├── static/               # Static files
├── manage.py
├── requirements.txt
└── ...
```

### 2. Create and Activate a Virtual Environment
```bash
python -3.11 -m venv venv311
# On Windows:
venv311\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the project root with the following content (adjust as needed):

```
# Django Configurations
SECRET_KEY=your_secret_key

# MySQL Database Configurations
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=127.0.0.1
DB_PORT=3306

# Neo4j Database Configurations
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

> **Note:**  
> After cloning the repository, open `testdj/settings.py` and update the `BASE_DIR` variable to match the path where you cloned the project on your machine.


> **Deployment Note:**  
> If you deploy this app on a public server, update the `ALLOWED_HOSTS` variable in `testdj/settings.py` to include your server’s domain name or public IP address (e.g., `['yourdomain.com', 'your.server.ip']`).  
> This is required for Django to serve requests from external users.

### 5. Setting Up the MySQL Database
1. **Install MySQL**  
   Make sure MySQL is installed and running on your system.

2. **Create the Database**  
   Open your MySQL client (e.g., MySQL Workbench, command line, etc.) and create a new database:
   ```sql
   CREATE DATABASE plaqueMS CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
   ```

3. **Import the Dumped SQL File**  
   Use the command line to import the provided SQL dump (`plaquems_database.sql`):

   ```bash
   mysql -u <your_mysql_user> -p plaqueMS < plaquems_database.sql
   ```
   - Replace `<your_mysql_user>` with your MySQL username.
   - Enter your password when prompted.

4. **Update Django Settings**  
   Make sure your `settings.py` (or `.env` file) has the correct database credentials:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'plaqueMS',
           'USER': '<your_mysql_user>',
           'PASSWORD': '<your_mysql_password>',
           'HOST': 'localhost',
           'PORT': '3306',
       }
   }
   ```
   
>**Automatic Database Creation:**
>When you start the application, it will attempt to create the MySQL database automatically if it does not already exist.
>Make sure your MySQL user has sufficient privileges to create databases.
>
>**Note:** If the database is created automatically (without importing the provided SQL dump), additional migration and data population steps are required to initialize the schema and load data.
These scripts exist but are **not documented in this guide.**

### 6. Setting Up the Neo4j Database
1. **Install Neo4j**  
   Make sure Neo4j Desktop is installed and running on your system.

2. **Create a New Project and Add a DBMS**  
   - Open Neo4j Desktop.
   - Create a new project (or use an existing one).
   - Within the project, click "Add" → "Local DBMS" to create a new DBMS (e.g., Neo4j 5.24.2).
   - Set a password.
    
3. **Locate the Neo4j Folders**  
   - After the DBMS is created, click on it in the sidebar, then click the `⋯` menu and select **"Open Folder"** → **DBMS** to access its directories.
   - Inside that folder, find:
       - The `bin/` directory — used to run the `neo4j-admin` command
       - The `import/` folder — where you will place your `.dump` file

4. **Place the Dump File**  
   - Copy your `.dump` file (e.g., `plaquems_neo4j_database.dump`) into the `import` folder you found above.
     
> **Note:** The `plaquems_neo4j_database.dump` file can be provided by the authors upon request, as it contains patient-sensitive data and is not publicly distributed.

5. **Restore the Dumped Database**  
   - Make sure the DBMS is stopped if running in Neo4j Desktop.
   - Run the following command from Git Bash (update paths as needed):
     ```bash
     "/c/Users/YourUsername/.Neo4jDesktop/relate-data/dbmss/dbms-<your-dbms-id>/bin/neo4j-admin.bat" database load --database=plaquems --from-path="/c/Users/YourUsername/.Neo4jDesktop/relate-data/dbmss/dbms-<your-dbms-id>/import" --overwrite-destination=true
     ```
   - Replace:
       - `YourUsername` → with your actual Windows username
       - `<your-dbms-id>` → with the unique folder name of your Neo4j DBMS instance (e.g., dbms-3fc316d9-...)
       - `plaquems` → with your desired database name.

6. **Restart the Database**  
   - In Neo4j Desktop, start the DBMS — the `plaquems` database should now appear and contain your data.

7. **Update Django Settings**  
   Make sure your `.env` or `settings.py` file contains the correct Neo4j connection details:
   ```
   NEO4J_URI=neo4j://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_neo4j_password
   NEO4J_DATABASE=plaquems
   ```














Enter python3 manage.py runserver 127.0.0.1:8000 on the command line to get the application running. You may need to install some other Python libraries; please follow the instructions in PyCharm to install them.  

Download the clusterMaker2 plugin from the Cytoscape app store. Click Apps--clusterMaker Cluster Network--MCL Cluster and check this box Create new clustered network in advance.  
### Data preparation:
Please prepare the PlaqueMS dataset and put it into the static folder in the Django project. Please ensure that all the documents inside have been decompressed, please pay special attention to the _bplot folder. And try to make sure there are no empty folder. I have made some adjustments to the data in the dataset, please paste the Statistics folder from the old dataset Plaque_MS all the way into the PlaqueMS/Carotid_Plaques_Vienna_Cohort folder. Please paste the Networks files in Plaque_MS under the corresponding experiments folder in PlaqueMS.  

You can run 127.0.0.1:8000/format/ to replace all the spaces in the filenames and file path with underscores, please check all the files and make sure there are no spaces in the folder name and file name before proceeding to the following operation. If this interface is not executed successfully, please click on the file insert\_views.py to modify the value of fpath to the path of the current dataset. You can replace this value with the location of the inner folder to ensure accuracy.  

This project requires a dataset for visualization, all relative paths are used in insert_views.py, please follow this path to insert. If you have path problem, please check insert_views.py for more detail about file path.  

Please prepare the protein dataset and put it into the static folder in the Django project. The file should be named HUMAN_9606_idmapping.dat  

you may need to edit the MySql database information in testdj/settings.py. Or you can create a new database named PlaqueMS  

after everything above is done, type python3 manage.py makemigrations in the command line, then type python3 manage.py migrate. Django can automatically generate database table creation scripts and insert them in MySQL.  

then is the website data initialization; please first import the data of datasets table; datasets.sql file can be found in the project folder.  

type 127.0.0.1:8000/insert_two/ in your browser to insert the contents of the second dataset  

type 127.0.0.1:8000/insert_three/ in your browser to insert the contents of the third dataset  

type 127.0.0.1:8000/insert_diff/ in your browser to insert the diff_exp_result files

type 127.0.0.1:8000/tree/ in your browser to save the folder tree structure data to a JSON file  

Enter 127.0.0.1:8000/network_json/ in the browser to save the data of the network file tree structure to the JSON file, and the data initialization is complete.   

type 127.0.0.1:8000/insert_proteins/ to insert protein data into database.  
### Explore:
Enter http://127.0.0.1:8000/index in the browser to open to the home page of the website.  

There are three tabs on the top of the website; you can reach three interfaces.  

The Protein page can be used to perform a joint query on the ids, or you can type in the ids and hit enter to perform a search. Visualization page can be a click-trigger search. Network page, please click the help button on the sidebar and follow the steps to use it.

