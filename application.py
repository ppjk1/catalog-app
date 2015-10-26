import os
import httplib2
import json
import datetime

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

# Configure app and extensions
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
csrf = SeaSurf(app)

# Connect to database
engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

# Create database session
DBSession = sessionmaker(bind=engine)
dbsession = DBSession()


# Login/authorize routes and functions

# Facebook login handler
@app.route('/fblogin')
def fblogin():

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

# Facebook auth redirect
@app.route('/fboauth2redirect')
def fboauth2redirect():

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

# Google login handler
@app.route('/glogin')
def glogin():

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


# Google auth redirect
@app.route('/goauth2redirect')
def goauth2redirect():

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


# Clears the session. Does NOT revoke 3rd party authorizations.
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# Redirects to a deauthorization confirmation page.
@app.route('/deauthorize')
def deauthorize():
    return render_template('deauthorize.html', provider=session['provider'])


# Calls appropriate deauthorization function and then redirects to logout to
# clear the session.
@app.route('/disconnect')
def disconnect():
    if session['provider'] == 'google':
        glogout()
    elif session['provider'] == 'facebook':
        fblogout()
    return redirect(url_for('logout'))


# Deauthorize Google
def glogout():
    credentials = client.OAuth2Credentials.from_json(session['credentials'])
    credentials.revoke(httplib2.Http())


# Deauthorize Facebook
def fblogout():
    facebook_id = session['facebook_id']
    access_token = session['facebook_token']['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (
        facebook_id, access_token)
    h = httplib2.Http()
    h.request(url, 'DELETE')[1]


# Primary routes
#  - Based on permalinks, rather than IDs
#  - SeaSurf extension provides CSRF protection for POST requests; requires
#    no extra work on our end beyond including _csrf_token in all forms.

@app.route('/')
@app.route('/catalog')
def index():
    categories = dbsession.query(Category).all()
    latest = dbsession.query(Item).order_by(
        Item.created_at.desc()).limit(10).all()
    return render_template('index.html', categories=categories, latest=latest)


@app.route('/catalog/<string:c_permalink>')
def showCategory(c_permalink):
    categories = dbsession.query(Category).all()
    # Avoid second database query by running loop in already retrieved data
    for c in categories:
        if c.permalink == c_permalink:
            category = c
            break
    items = dbsession.query(Item).filter_by(category_id=category.id).all()
    return render_template(
        'items.html', category=category, categories=categories, items=items)


@app.route('/catalog/<string:c_permalink>/<i_permalink>')
def showItem(c_permalink, i_permalink):
    category = dbsession.query(Category).filter_by(
        permalink=c_permalink).one()
    item = dbsession.query(Item).filter_by(permalink=i_permalink).one()
    return render_template(
        'item-detail.html', item=item, category=category)


@app.route('/catalog/<string:c_permalink>/new', methods=['POST', 'GET'])
def newItem(c_permalink):

    # Non-logged in users should not be allowed to create items.
    if 'username' not in session:
        flash('Please log in to add new items.')
        return redirect(url_for('index'))

    # Create the new item
    if request.method == 'POST':
        newItem = Item(
            category_id=int(request.form['category']),
            name=request.form['name'],
            permalink=request.form['name'].lower().replace(
                ' ', '-').translate("'"),
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
        dbsession.commit()
        flash('Item successfully created.')
        return redirect(url_for('showCategory', c_permalink=c_permalink))
    else:
        categories = dbsession.query(Category).all()
        return render_template('item-new.html', categories=categories)


@app.route('/catalog/<string:i_permalink>/edit', methods=['POST', 'GET'])
def editItem(i_permalink):

    # Non-logged in users should not be allowed to edit items.
    if 'username' not in session:
        flash('Please log in to manage your items.')
        return redirect(url_for('index'))

    # Database queries
    item = dbsession.query(Item).filter_by(permalink=i_permalink).one()
    categories = dbsession.query(Category).all()
    for c in categories:
        if c.id == item.category_id:
            category = c
            break

    # User should not be allowed to edit other users' items.
    if item.user_id != session['user_id']:
        return redirect(
            url_for('showItem', c_permalink=category.permalink,
                    i_permalink=item.permalink))

    # Update item
    if request.method == 'POST':
        if request.form['category']:
            item.category_id = request.form['category']
        if request.form['name']:
            item.name = request.form['name']
            item.permalink = request.form['name'].lower().replace(
                ' ', '-').translate("'")
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
            url_for('showCategory', c_permalink=category.permalink))
    else:
        return render_template('item-edit.html', category=category,
                               categories=categories, item=item)


# File upload utility function
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@app.route('/catalog/<string:i_permalink>/delete', methods=['POST', 'GET'])
def deleteItem(i_permalink):

    # Non-logged in users should not be allowed to delete items.
    if 'username' not in session:
        flash('Please log in to manage your items.')
        return redirect(url_for('index'))

    # Database queries
    item = dbsession.query(Item).filter_by(permalink=i_permalink).one()
    category = dbsession.query(Category).filter_by(
        id=item.category_id).one()

    # Users should not be allowed to delete other users' items.
    if item.user_id != session['user_id']:
        return redirect(
            url_for('showItem', c_permalink=category.permalink,
                    i_permalink=item.permalink))

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
            url_for('showCategory', c_permalink=category.permalink))
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
    categories = dbsession.query(Category).all()
    catalog = []
    for c in categories:
        catalog.append(c.serialize)
        items = dbsession.query(Item).filter_by(category_id=c.id).all()
        catalog[-1]['items'] = [i.serialize for i in items]
    response = make_response(render_template('catalog.xml', catalog=catalog))
    response.headers['Content-Type'] = 'application/xml'
    return response


if __name__ == "__main__":
    app.secret_key = '\x7f\x99\xe9\x91XjH?\x10\xe71\xa9My\x8d\xdb\xa2\xa8q0\xef\xda\x07\x8f'  # noqa
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
