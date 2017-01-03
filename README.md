# Instructions for running the goodrx script
1. Download chromedriver for your OS: https://sites.google.com/a/chromium.org/chromedriver/downloads
2. Place the chromedriver file (make sure it's named chromedriver in lowercase) in the same directory as the script
3. Download git bash, the terminal emulator: https://git-scm.com/downloads
4. Create an input csv file for the script to accept, and place it in the same directory as the script
* The input file has 6 columns
* The input file assumes the first row of data is the column headers, which are as follows: "Drug name | Form | Dosage | Quantity | Label Override | Zip/Location"
5. Record the absolute path of the directory containing the script:
* Navigate to the directory containing the script in the windows file Explorer
* Shift+right click the directory containing the script, and select "Copy as path"
6. Open git bash
7. Using the absolute path from step 5 enter this command: `cd "<absolute path>"`
8. Run the script in this manner, here are the command line args:
`./goodrx.exe "<input csv file>" "<browsers to search>" <wait time> `
Args:
    <input csv file> - It's the file from step 4, make sure to put it in quotes and with .csv extension
    <browser to search> - spell out the names Chrome, Internet Explorer, and/or Safari in quotes.  Can add all or just Online
    <wait time> - Max time for page loads before timing out.  Put something like 3 if your internet is very good.  Avg internet put 5.  Bad internet, 10.
