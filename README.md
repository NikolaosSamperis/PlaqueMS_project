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
├── manage.py
├── login/    # Main Django app
│   ├── __init__.py    # Marks directory as python package
│   ├── admin.py    # Admin interface config. for models (not used)
│   ├── apps.py    # App config. settings
│   ├── auth_views.py    # User authentication back-end (login, register, logout)
│   ├── calc_pred_views.py    # "Calcification prediction" tool back-end
│   ├── cyviews.py    # "Protein Networks" tool back-end (Cytoscape-based)
│   ├── forms.py    # Django form classes for user input/validation
│   ├── home_views.py    # Home page back-end
│   ├── insert_views.py    # Script for inserting data in the MySQL database (ignore)
│   ├── management    # Scripts for populating the database (ignore)
│   │   ├── __init__.py
│   │   └── commands
│   │       ├── __init__.py
│   │       ├── insert_uva.py
│   │       └── insert_vienna.py    
│   ├── migrations    # Database migration files for MySQL (ignore)
│   │   ├── 0001_initial.py
│   │   └── __init__.py
│   ├── models.py    # Django ORM models defining MySQL database schema
│   ├── networkTree.py    # Builds and saves a filtered experiment/network tree as JSON (legacy, ignore)
│   ├── pathTree.py    # Builds a hierarchical dataset/experiment tree and saves it as JSON (legacy, ignore)
│   ├── plaquery_views.py    # "Protein Abundance" tool back-end
│   ├── plot_views.py    # "Differential Analysis Results" tool back-end
│   ├── protein_views.py    # "Proteins" tool back-end
│   ├── syntax_score_views.py    # "Syntax score prediction" tool back-end
│   ├── templates    # HTML front-end templates
│   │   ├── Home.html
│   │   ├── calc_pred.html
│   │   ├── login
│   │   │   ├── admin_dashboard.html
│   │   │   ├── login.html
│   │   │   └── register.html
│   │   ├── network.html
│   │   ├── plaquery.html
│   │   ├── plot.html
│   │   ├── plot_result_list.html
│   │   ├── protein.html
│   │   └── syntax_pred.html
│   ├── templatetags    # Custom template tags for use in Django templates
│   │   ├── __init__.py
│   │   ├── auth_extras.py
│   │   └── navigation.py
│   ├── tests.py    # Unit and integration tests for the app (legacy, ignore)
│   └── validators.py    # Custom validation logic for forms.py
├── testdj/    # Django project config. directory
│   ├── __init__.py
│   ├── asgi.py    # ASGI entry point for asynchronous server deployments (legacy)
│   ├── settings.py    # Main Django settings file (config.)
│   ├── urls.py    # URL routing for the project
│   └── wsgi.py    # WSGI entry point for server deployments (legacy)
├── static/    # static files and datasets for the app
│   ├── .ipynb_checkpoints    # Jupyter notebook checkpoint files (ignore)
│   ├── Dictionary_all.csv    # Protein annotation dictionary for "Protein Abundance" tool
│   ├── HUMAN_9606_idmapping.dat    # Protein ID mapping (used to populate MySQL database, not needed)
│   ├── PlaqueMS    # Main datasets
│   ├── Untitled.ipynb    # ignore
│   ├── __init__.py
│   ├── calcified_vs_noncalcified_periphery_vp.jpg    # JPG used in the "Home page"
│   ├── geometric-heart-scaled.png    # JPG used in the "Home page"
│   ├── heatmap_all.png    # JPG used in the "Home page"
│   ├── heatmap_significant_corrected.png    # JPG used in the "Home page"
│   └── symptomatic_vs_asymptomatic_periphery_vp.jpg    # JPG used in the "Home page"
└── model_artifacts/    # Pre-trained models and related files for predictions
    ├── Cellular_Proteome
    │   ├── 0finalSingleModel.pkl
    │   ├── FeatureMaxNormdata.csv    # ignore
    │   ├── FeatureMinNormdata.csv    # ignore
    │   ├── knn_imputer.pkl
    │   ├── minmax_scaler.pkl
    │   ├── sds_new_input.txt    # ignore
    │   └── selected_features_best_model.csv    # ignore
    ├── Core_Matrisome
    │   ├── 0finalSingleModel.pkl
    │   ├── FeatureMaxNormdata.csv    # ignore
    │   ├── FeatureMinNormdata.csv    # ignore
    │   ├── guhcl_new_input.txt    # ignore
    │   ├── knn_imputer.pkl
    │   ├── minmax_scaler.pkl
    │   └── selected_features_best_model1.csv    # ignore
    ├── GUHCL_syntax_score
    │   └── syntax_pipeline.pkl
    └── Soluble_Matrisome
        ├── 0finalSingleModel.pkl
        ├── FeatureMaxNormdata.csv    # ignore
        ├── FeatureMinNormdata.csv    # ignore
        ├── knn_imputer.pkl
        ├── minmax_scaler.pkl
        ├── nacl_new_input.txt    # ignore
        └── selected_features_best_model.csv    # ignore
```

>**Note:** The `static` directory is not included in the cloned repository due to its large size. It can be provided by the authors upon request.

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

### 8. Create a Superuser (Admin)
```bash
python manage.py createsuperuser
```

### 9. Run the Development Server locally
```bash
python manage.py runserver
```

## Troubleshooting
- **MySQL errors:** Check your `.env` and MySQL server status.
- **Neo4j errors:** Ensure Neo4j is running and credentials are correct.
- **Cytoscape Desktop requirements:** Ensure that Cytoscape Desktop is running in the background with the `clusterMaker2` plugin installed. Additionally, in Cytoscape, go to `Apps → clusterMaker Cluster Network → MCL Cluster` and enable the `Create new clustered network` option. This is required to view Markov clustering results in the "Protein Networks" module.
- **Windows file path issues:** On Windows 10 or later, enable long path support to prevent file paths from becoming inaccessible, even if they are correctly stored in the MySQL database. Run the following command in PowerShell as Administrator:
```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```
Then restart your system for the changes to take effect.


## License



## Contact
For questions, contact [Nikolaos Samperis](mailto:nick.saberis@yahoo.com).


