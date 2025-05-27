# PlaqueMS
## User Guide
### Preparation: 
Download Python, Django, Cytoscape, and MySQL and install them. Please download according to the version in this table to avoid conflicts.  

MySQL  8.0.26  
Cytoscape 3.10.0  
clusterMaker2 2.3.4  
Python 3.8  
Django 3.2.4  
Django Rest Framework 3.12.0  
py4cytoscape 1.7.0  

Install python ide; I recommend using PyCharm and importing the code into PyCharm.  

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

