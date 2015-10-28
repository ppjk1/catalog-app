import os
import httplib2
import json
import datetime

from functools import wraps
from flask import Flask, session, redirect, render_template, request, url_for,\
    flash, jsonify, make_response
from werkzeug import secure_filename
from flask.ext.seasurf import SeaSurf

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dbsetup import Base, User, Category, Item

from oauth2client import client
from apiclient import discovery

# Configuration for picture uploads
UPLOAD_FOLDER = '/vagrant/catalog/static/images'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])
UPLOAD_FILESIZE_LIMIT = 4 * 1024 * 1024  # 4 megabytes

# Configure app and extensions
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = UPLOAD_FILESIZE_LIMIT
csrf = SeaSurf(app)

# Connect to database
engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

# Create database session
DBSession = sessionmaker(bind=engine)
dbsession = DBSession()


# Login/authorize routes and functions

@app.route('/fblogin')
def fblogin():
    """Handles Facebook login.

    Redirects to Facebook authentication dialog if user is not logged in.
    Retrieves user data and redirects to '/' if user is logged in.
    """

    # If not logged in, redirect to Facebook login
    if 'facebook_token' not in session:
        app_id = json.loads(open('fb_client_secrets.json', 'r').read())[
            'web']['app_id']
        return redirect('https://www.facebook.com/dialog/oauth?client_id=%s&redirect_uri=http://localhost:8000/fboauth2redirect&scope=public_profile,email' % app_id)  # noqa

    # Fetch user data
    token = session['facebook_token']['access_token']
    url = 'https://graph.facebook.com/v2.5/me?access_token=%s&fields=name,id,email,picture' % (token)  # noqa
    h = httplib2.Http()
    data = json.loads(h.request(url, 'GET')[1])

    if 'error' in data:
        response = make_response(json.dumps(data), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    if data['id'] != session['facebook_id']:
        response = make_response(json.dumps(
            "Token's user id doesn't match given user id."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    session['provider'] = 'facebook'
    session['username'] = data['name']
    session['email'] = data['email']
    session['picture'] = data['picture']['data']['url']

    # See if user exists
    user_id = getUserID(session['email'])
    if not user_id:
        user_id = createUser(session)
    session['user_id'] = user_id

    return redirect(url_for('index'))


@app.route('/fboauth2redirect')
def fboauth2redirect():
    """Handles Facebook authentication redirect.

    Receives authentication code, exchanges code for access token, verifies
    token and redirects to '/fblogin' for user data retrieval.
    """

    # User denied Facebook auth request
    if 'error' in request.args:
        return redirect(url_for('index'))

    # Retrieve authentication code returned by Facebook
    auth_code = request.args.get('code')

    # Retrieve app_id and app_secret for Facebook
    app_id = json.loads(open('fb_client_secrets.json', 'r').read())[
        'web']['app_id']
    app_secret = json.loads(open('fb_client_secrets.json', 'r').read())[
        'web']['app_secret']

    # Exchange auth code for user access token
    url = 'https://graph.facebook.com/v2.3/oauth/access_token?client_id=%s&redirect_uri=http://localhost:8000/fboauth2redirect&client_secret=%s&code=%s' % (app_id, app_secret, auth_code)  # noqa
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    if 'access_token' in result:
        session['facebook_token'] = result
    elif 'error' in result:
        response = make_response(json.dumps(result), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify user access token
    token = session['facebook_token']['access_token']
    url = 'https://graph.facebook.com/debug_token?input_token=%s&key=value&access_token=%s|%s' % (token, app_id, app_secret)  # noqa
    h = httplib2.Http()
    data = json.loads(h.request(url, 'GET')[1])['data']
    if data['app_id'] != app_id:
        response = make_response(json.dumps(
            'Failed to verify the access token.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    if data['is_valid'] != True:
        response = make_response(json.dumps(
            'Access token is no longer valid.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    session['facebook_id'] = data['user_id']
    return redirect(url_for('fblogin'))


@app.route('/glogin')
def glogin():
    """Handles Goolge login.

    Redirects to '/goauth2redirect' if user is not logged in.
    Retrieves user data and redirects to '/' if user is logged in.
    """

    # If not logged in, redirect to Google login
    if 'credentials' not in session:
        return redirect(url_for('goauth2redirect'))

    credentials = client.OAuth2Credentials.from_json(session['credentials'])
    if credentials.access_token_expired:
        return redirect(url_for('goauth2redirect'))
    else:
        # Authorize and build a service object to retrieve user data
        http_auth = credentials.authorize(httplib2.Http())
        service = discovery.build('oauth2', 'v2', http=http_auth)
        request = service.userinfo().v2().me().get()
        response = request.execute()

        session['provider'] = 'google'
        session['username'] = response['name']
        session['google_id'] = response['id']
        session['picture'] = response['picture']
        session['email'] = response['email']

        # See if user exists
        user_id = getUserID(session['email'])
        if not user_id:
            user_id = createUser(session)
        session['user_id'] = user_id

    return redirect(url_for('index'))


@app.route('/goauth2redirect')
def goauth2redirect():
    """Handles Google authentication flow.

    Builds a login flow object. Redirects user to Google authentication
    dialog if user is not logged in. Once user logs in, retrieves
    authorization code and upgrades code for credentials object. Then
    redirects to '/glogin' for user data retrieval.
    """

    # Build a flow object
    flow = client.flow_from_clientsecrets(
          'g_client_secrets.json',
          scope=['https://www.googleapis.com/auth/plus.me',
                 'https://www.googleapis.com/auth/userinfo.email'],
          redirect_uri=url_for('goauth2redirect', _external=True))
    if 'code' not in request.args:
        # Get authorization code via redirect to Google authorization page
        auth_uri = flow.step1_get_authorize_url()
        return redirect(auth_uri)
    else:
        # Upgrade authorization code for credentials object
        auth_code = request.args.get('code')
        credentials = flow.step2_exchange(auth_code)
        session['credentials'] = credentials.to_json()
        return redirect(url_for('glogin'))


# User helper functions

def createUser(session):
    """Creates a new user record.

    Args:
        session: A Flask session object populated with 'username', 'email',
                 and 'picture' attributes.
    Returns:
        newUser.id: The numerical id of the newly created user record.
    """
    newUser = User(
                name=session['username'],
                email=session['email'],
                picture=session['picture'])
    dbsession.add(newUser)
    # Flushing allows us to grab the new id before committing.
    dbsession.flush()
    dbsession.commit()
    return newUser.id


def getUserID(email):
    """Retrieves a user record.

    Args:
        email: A string email address to filter on in user lookup.
    Returns:
        user.id: The numerical id of the user record if found.
        None:   If user record was not found.
    """
    try:
        user = dbsession.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# Log out and deauthorize routes/functions
#
#   Follows Facebook recommended best practices:
#
#   - By default, only delete session data on the server. The user should not
#     have to reauthorize your app every time they log in.
#
#   - Provide separate mechanism for disabling 3rd party authorization,
#     available via footer link.


@app.route('/logout')
def logout():
    """Clears the Flask session."""
    session.clear()
    return redirect(url_for('index'))


@app.route('/deauthorize')
def deauthorize():
    """Redirects to a deauthorization confirmation page."""
    return render_template('deauthorize.html', provider=session['provider'])


@app.route('/disconnect')
def disconnect():
    """Deauthorizes user and redirects to '/logout' to clear the session."""
    if session['provider'] == 'google':
        glogout()
    elif session['provider'] == 'facebook':
        fblogout()
    return redirect(url_for('logout'))


def glogout():
    """Deauthorizes user from Google using the credentials object."""
    credentials = client.OAuth2Credentials.from_json(session['credentials'])
    credentials.revoke(httplib2.Http())


def fblogout():
    """Deauthorizes the user from Facebook using stored session data."""
    facebook_id = session['facebook_id']
    access_token = session['facebook_token']['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (
        facebook_id, access_token)
    h = httplib2.Http()
    h.request(url, 'DELETE')[1]


# Primary routes
#  - SeaSurf extension provides CSRF protection for POST requests; requires
#    no extra work on our end beyond including _csrf_token in all forms.

def login_required(func):
    """Function decorator that controls user permissions.

    Prevents non-logged in users from performing Create, Update, or Delete
    operations by redirecting to '/'.

    Args:
        func: The function to decorate.
    Returns:
        decorated_function: The newly decorated function with added permission
                            controls.
    """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to manage items.')
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return decorated_function


@app.route('/')
@app.route('/catalog')
def index():
    """Route for site index.

    Retrieves all categories for site menu.
    Retrieves latest items added.

    Returns:
        index.html
    """
    categories = dbsession.query(Category).all()
    latest = dbsession.query(Item).order_by(
        Item.created_at.desc()).limit(10).all()
    return render_template('index.html', categories=categories, latest=latest)


@app.route('/catalog/<int:category_id>')
def showCategory(category_id):
    """Route for a single category.

    Retrieves all items for the given category.
    Retrieves all categories for site menu.

    Args:
        category_id: A numerical category id for item lookup.
    Returns:
        items.html
    """
    categories = dbsession.query(Category).all()
    # Avoid second database query by running loop in already retrieved data
    for c in categories:
        if c.id == category_id:
            category = c
            break
    items = dbsession.query(Item).filter_by(category_id=category.id).all()
    return render_template(
        'items.html', category=category, categories=categories, items=items)


@app.route('/catalog/<int:category_id>/<item_id>')
def showItem(category_id, item_id):
    """Route for a single item.

    Retrieves an item record and its parent category record.

    Returns:
        item-detail.html
    """
    category = dbsession.query(Category).filter_by(
        id=category_id).one()
    item = dbsession.query(Item).filter_by(id=item_id).one()
    return render_template(
        'item-detail.html', item=item, category=category)


@app.route('/catalog/<int:category_id>/new', methods=['POST', 'GET'])
@login_required
def newItem(category_id):
    """Route for new item creation.

    Args:
        category_id: A numerical category id. Item creation is not restricted
                     to this category, however.
    Returns:
        GET: item-new.html - form with inputs for item creation
        POST: redirect to 'showCategory' after creating new item record
    """
    # Create the new item
    if request.method == 'POST':
        newItem = Item(
            category_id=int(request.form['category']),
            name=request.form['name'],
            description=request.form['description'],
            created_at=datetime.datetime.now(),
            user_id=session['user_id'])

        # Handle picture upload (if present)
        file = request.files['picture']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            newItem.picture = filename

        dbsession.add(newItem)
        dbsession.flush()
        dbsession.commit()
        flash('Item successfully created.')
        return redirect(
            url_for('showItem', category_id=category_id, item_id=newItem.id))
    else:
        categories = dbsession.query(Category).all()
        return render_template('item-new.html', categories=categories)


@app.route('/catalog/<int:item_id>/edit', methods=['POST', 'GET'])
@login_required
def editItem(item_id):
    """Route to edit a single item.

    Args:
        item_id: A numerical item id.
    Returns:
        GET: item-edit.html - form with inputs to edit item details
        POST: redirect to 'showCategory' after updating item record
    """
    # Database queries
    item = dbsession.query(Item).filter_by(id=item_id).one()
    categories = dbsession.query(Category).all()
    for c in categories:
        if c.id == item.category_id:
            category = c
            break

    # User should not be allowed to edit other users' items.
    if item.user_id != session['user_id']:
        return redirect(
            url_for('showItem', category_id=category.id,
                    item_id=item.id))

    # Update item
    if request.method == 'POST':
        if request.form['category']:
            item.category_id = request.form['category']
        if request.form['name']:
            item.name = request.form['name']
        if request.form['description']:
            item.description = request.form['description']
        item.updated_at = datetime.datetime.now()

        # Handle picture upload (if present)
        file = request.files['picture']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # Remove old photo from filesystem
            if item.picture:
                path = "%s/%s" % (app.config['UPLOAD_FOLDER'], item.picture)
                os.remove(path)
            # Update item's picture
            item.picture = filename

        dbsession.add(item)
        dbsession.commit()
        flash('Item succesfully updated.')
        return redirect(
            url_for('showItem', category_id=category.id, item_id=item.id))
    else:
        return render_template('item-edit.html', category=category,
                               categories=categories, item=item)


def allowed_file(filename):
    """Checks format of an uploaded file.

    Compares file extension to global list object.

    Args:
        filename: The filename of an uploaded file.
    Returns:
        Boolean value
    """
    return '.' in filename and \
        filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@app.route('/catalog/<int:item_id>/delete', methods=['POST', 'GET'])
@login_required
def deleteItem(item_id):
    """Route for item deletion.

    Args:
        item_id: A numerical item id.
    Returns:
        GET: item-delete.html - form for confirmation prior to deletion
        POST: redirect to 'showCategory' after item record deletion
    """
    # Database queries
    item = dbsession.query(Item).filter_by(id=item_id).one()
    category = dbsession.query(Category).filter_by(
        id=item.category_id).one()

    # Users should not be allowed to delete other users' items.
    if item.user_id != session['user_id']:
        return redirect(
            url_for('showItem', category_id=category.id,
                    item_id=item.id))

    # Delete item
    if request.method == 'POST':
        # Delete item's picture from filesystem
        if item.picture:
            path = "%s/%s" % (app.config['UPLOAD_FOLDER'], item.picture)
            os.remove(path)
        # Delete item from database
        dbsession.delete(item)
        dbsession.commit()
        flash('Item successfully deleted.')
        return redirect(
            url_for('showCategory', category_id=category.id))
    else:
        return render_template(
            'item-delete.html', category=category, item=item)


# API Endpoint routes
#  - Single call returns all data:
#      Build catalog array of serialized categories with serialized items
#      nested by category

@app.route('/json')
@app.route('/catalog/json')
def indexJSON():
    """Route for JSON endpoint."""
    categories = dbsession.query(Category).all()
    catalog = []
    for c in categories:
        catalog.append(c.serialize)
        items = dbsession.query(Item).filter_by(category_id=c.id).all()
        catalog[-1]['items'] = [i.serialize for i in items]
    # Jsonify automatically builds Response object with correct MIME type and
    # content-type header
    return jsonify(Categories=catalog)


@app.route('/xml')
@app.route('/catalog/xml')
def indexXML():
    """Route for XML endpoint."""
    categories = dbsession.query(Category).all()
    catalog = []
    for c in categories:
        catalog.append(c.serialize)
        items = dbsession.query(Item).filter_by(category_id=c.id).all()
        catalog[-1]['items'] = [i.serialize for i in items]
    response = make_response(render_template('catalog.xml', catalog=catalog))
    response.headers['Content-Type'] = 'application/xml'
    return response


@app.errorhandler(413)
def upload_size_error(e):
    """Catches 413 error from filesize limit enforced on photo uploads.

    Args:
        e: Error object
    Returns:
        413.html
    """
    return render_template('413.html'), 413


if __name__ == "__main__":
    app.secret_key = '\x7f\x99\xe9\x91XjH?\x10\xe71\xa9My\x8d\xdb\xa2\xa8q0\xef\xda\x07\x8f'  # noqa
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
