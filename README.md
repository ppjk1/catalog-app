# Music for the Masses #

A basic catalog app demonstrating CRUD functionality and 3rd party authentication/authorization integrations for login and user permissions.

- Categories of musical instruments are pre-defined.
- Non-logged in users may view all items in the database and may access API endpoints.
- Logged in users may add new items and edit or delete items they have previously created.

## Requirements ##
- [Python 2.7][1]
- [Flask][2]
- [SQLAlchemy][3]
- [httplib2][4]
- [Google API Python Client][5]
- [SeaSurf][6]

#### Additional Requirements ####
- Google and Facebook client secrets files are also required for app functionality and should be copied into the root directory of the app. These files will be provided to Udacity reviewers via separate zip file upload.

## Quickstart ##
- Ensure you have the required software installed (see Requirements)
- To install the Google API Python Client:


    $ pip install --upgrade google-api-python-client
    or
    $ easy_install --upgrade google-api-python-client

- Clone the repo:
        git clone https://github.com/ppjk1/catalog-app.git
- Use a terminal to navigate into the **catalog-app** directory
- Set up the database: `python dbsetup.py`
- Populate the database: `python populatedb.py`
- Run the app: `python application.py`
- Navigate to the app via a web browser: `http://localhost:8000`

## 3rd Party Authentication Providers ##
The app allows a user to log in via a Google or Facebook account via a login link in the header of each page.

#### Log Out / De-authorization ####
Following Facebook recommended best practices, by default when a user clicks the **Log Out** link, the app clears the session but does NOT de-authorize the user. This streamlines the login process when the user next accesses the app.

A user may de-authorize the app at any time either through the native Facebook or Google interfaces, or via a link in the footer of the site.

## API Endpoints ##
Aggregated catalog data can be downloaded via API endpoints (links are also available in the footer of each page):
- JSON: http://localhost:8000/catalog/json
- XML: http://localhost:8000/catalog/xml

## What's Included ##
Within the download, you'll find the following files:
```
catalog/
  |--- README.md
  |--- application.py
  |--- dbsetup.py
  |--- populatedb.py
  |--- static/
       |--- css/
            |--- normalize.css
            |--- skeleton.css
            |--- styles.css
       |--- images/
            |--- footer_lodyas/
                 |--- footer_lodyas.png
                 |--- readme.txt
            |--- acoustic-025174_1020.jpg
            |--- acoustic-guitar.jpg
            |--- banjo.jpg
            |--- bass-guitar.jpg
            |--- drums.jpg
            |--- electric-guitar.jpg
            |--- F_icon.svg
            |--- favicon.png
            |--- Google_plus.svg
            |--- guitar-amp.jpg
            |--- mandolin.jpg
            |--- pedals.jpg
            |--- Udacity_Logo.svg
            |--- ukelele.jpg
       |--- js/
            |--- menu.js
  |--- templates/
       |--- catalog.xml
       |--- deauthorize.html
       |--- index.html
       |--- item-delete.html
       |--- item-detail.html
       |--- item-edit.html
       |--- item-new.html
       |--- items.html
       |--- main.html
```

### Credits ###
- Front-end Framework: [Skeleton][7]
- Icons: [Font Awesome][8]
- Background Pattern: http://subtlepatterns.com
- Content and Header Images: https://pixabay.com
- Much of the project codebase builds upon work done in Udacity prep courses. Login flow, however, was built from scratch following Google and Facebook documentation.

[1]: https://www.python.org/downloads/
[2]: http://flask.pocoo.org
[3]: http://www.sqlalchemy.org
[4]: https://github.com/jcgregorio/httplib2
[5]: https://developers.google.com/api-client-library/python/guide/aaa_oauth
[6]: https://flask-seasurf.readthedocs.org/en/latest/
[7]: http://getskeleton.com
[8]: https://fortawesome.github.io/Font-Awesome/
