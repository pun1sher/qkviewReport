# qkviewReport
Create a word document from F5 Qkview hosted on iHealth.f5.com



##  Requirements:
The following will need to be installed:
* python-docx
* requests
* xmltodict 

## How to run:
python3 qkviewReport.py

Example:

python3 qkviewReport.py
Paste the link to the qkview: qkview link from iHealth
Enter customer name: demo
Retrieving Device Information
Retrieving Licensing Information
Retrieving Interface Information
Retrieving Object Counts
Retrieving graphs
Retrieving Diagnostic report data...

QkviewReport will create sub-folders qkview_output/<customer name>

The file will be created in the customer folder with the naming convention hostname_YYYY-MM-DD.docx, where YYYY-MM-DD is the generation date of the qkview.


