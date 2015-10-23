import httplib2
import json
import datetime

from flask import Flask, session, redirect, render_template, request, url_for,\
    flash, jsonify

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dbsetup import Base, User, Category, Item

from oauth2client import client
from apiclient import discovery

app = Flask(__name__)

engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
dbsession = DBSession()


# Retrieve app_id and app_secret for Facebook
FB_APP_ID = json.loads(open('fb_client_secrets.json', 'r').read())['web']['app_id']
FB_APP_SECRET = json.loads(open('fb_client_secrets.json', 'r').read())[
    'web']['app_secret']


# Login/authorize routes and functions


@app.route('/login')
def login():
    if request.args.get('permanent') == 'true':
        # Stores session for default 31 days (unless user logs out)
        session.permanent = True


@app.route('/fblogin')
def fblogin():
    if 'facebook_token' not in session:
        # note: should add 'state' parameter to this redirect for anti-CSRF
        return redirect('https://www.facebook.com/dialog/oauth?client_id=%s&redirect_uri=http://localhost:8000/fboauth2redirect&scope=public_profile,email' % FB_APP_ID)
    #   Fetch user data, check for user (create if none), and redirect to index
    token = session['facebook_token']['access_token']
    url = 'https://graph.facebook.com/v2.5/me?access_token=%s&fields=name,id,email,picture' % (token)
    h = httplib2.Http()
    data = json.loads(h.request(url, 'GET')[1])
#    if 'error' in data:
        # handle error
#        pass
    if data['id'] != session['facebook_id']:
        #handle error
        pass
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
    # Retrieve authentication code
    try:
        auth_code = request.args.get('code')
    except:
        # JH- need to handle error here
        # See: https://developers.facebook.com/docs/facebook-login/permissions/#missingperms
        return None

    # Exchange auth code for user access token
    url = 'https://graph.facebook.com/v2.3/oauth/access_token?client_id=%s&redirect_uri=http://localhost:8000/fboauth2redirect&client_secret=%s&code=%s' % (FB_APP_ID, FB_APP_SECRET, auth_code)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    if 'access_token' in result:
        session['facebook_token'] = result

    # Verify user access token
    token = session['facebook_token']['access_token']
    url = 'https://graph.facebook.com/debug_token?input_token=%s&key=value&access_token=%s|%s' % (token, FB_APP_ID, FB_APP_SECRET)
    h = httplib2.Http()
    data = json.loads(h.request(url, 'GET')[1])['data']
    if data['app_id'] != FB_APP_ID:
        # handle error
        pass
    if data['is_valid'] != True:
        # handle error
        pass
    session['facebook_id'] = data['user_id']
    return redirect(url_for('fblogin'))


@app.route('/glogin')
def glogin():
    if 'credentials' not in session:
        return redirect(url_for('goauth2redirect'))
    credentials = client.OAuth2Credentials.from_json(session['credentials'])
    if credentials.access_token_expired:
        return redirect(url_for('goauth2redirect'))
    else:
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
    flow = client.flow_from_clientsecrets(
          'g_client_secrets.json',
          scope=['https://www.googleapis.com/auth/plus.me',
                 'https://www.googleapis.com/auth/userinfo.email'],
          redirect_uri=url_for('goauth2redirect', _external=True))
    if 'code' not in request.args:
        auth_uri = flow.step1_get_authorize_url()
        return redirect(auth_uri)
    else:
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
    dbsession.flush()
    dbsession.commit()
    print "NEW USER ID: %s" % newUser.id
    return newUser.id


def getUserID(email):
    try:
        user = dbsession.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# Log out and deauthorize routes/functions

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/deauthorize')
def deauthorize():
    return render_template('deauthorize.html', provider = session['provider'])


@app.route('/disconnect')
def disconnect():
    if session['provider'] == 'google':
        glogout()
    elif session['provider'] == 'facebook':
        fblogout()
    return redirect(url_for('logout'))


def glogout():
    credentials = client.OAuth2Credentials.from_json(session['credentials'])
    credentials.revoke(httplib2.Http())


def fblogout():
    facebook_id = session['facebook_id']
    access_token = session['facebook_token']['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (facebook_id, access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]


# Primary routes


@app.route('/')
@app.route('/catalog')
def index():
    categories = dbsession.query(Category).all()
    latest = dbsession.query(Item).order_by(Item.created_at.desc()).limit(10).all()
    return render_template('index.html', categories=categories,
        latest = latest)


@app.route('/catalog/<string:c_permalink>/items')
def showCategory(c_permalink):
    categories = dbsession.query(Category).all()
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
    if request.method == 'POST':
        newItem = Item(
            category_id=request.form['category'],
            name=request.form['name'],
            permalink=request.form['name'].lower().replace(' ', '-').translate("'"),
            description=request.form['description'],
            created_at=datetime.datetime.now(),
            user_id=1)
        dbsession.add(newItem)
        dbsession.commit()
        return redirect(url_for('showCategory', c_permalink=c_permalink))
    else:
        categories = dbsession.query(Category).all()
        return render_template('item-new.html', categories=categories)


@app.route('/catalog/<string:i_permalink>/edit', methods=['POST', 'GET'])
def editItem(i_permalink):
    item = dbsession.query(Item).filter_by(permalink=i_permalink).one()
    categories = dbsession.query(Category).all()
    for c in categories:
        if c.id == item.category_id:
            category = c
            break
    if request.method == 'POST':
        if request.form['category']:
            item.category_id = request.form['category']
        if request.form['name']:
            item.name = request.form['name']
            item.permalink = request.form['name'].lower().replace(' ', '-').translate("'")
        if request.form['description']:
            item.description = request.form['description']
        item.updated_at = datetime.datetime.now()
        dbsession.add(item)
        dbsession.commit()
        return redirect(
            url_for('showCategory', c_permalink=category.permalink))
    else:
        return render_template('item-edit.html', category=category,
                               categories=categories, item=item)


@app.route('/catalog/<string:i_permalink>/delete', methods=['POST', 'GET'])
def deleteItem(i_permalink):
    item = dbsession.query(Item).filter_by(permalink=i_permalink).one()
    category = dbsession.query(Category).filter_by(
        id=item.category_id).one()
    if request.method == 'POST':
        dbsession.delete(item)
        dbsession.commit()
        return redirect(
            url_for('showCategory', c_permalink=category.permalink))
    else:
        return render_template(
            'item-delete.html', category=category, item=item)


# API Endpoint routes

@app.route('/json')
@app.route('/catalog/json')
def indexJSON():
    categories = dbsession.query(Category).all()
    catalog = []
    for c in categories:
        catalog.append(c.serialize)
        items = dbsession.query(Item).filter_by(category_id=c.id).all()
        catalog[-1]['items'] = [i.serialize for i in items]
    return jsonify(Categories=catalog)


@app.route('/catalog/<string:c_permalink>/json')
def showCategoryJSON(c_permalink):
    category = dbsession.query(Category).filter_by(permalink=c_permalink).one()
    items = dbsession.query(Item).filter_by(category_id=category.id)
    return jsonify(
        Category=category.name,
        Items=[i.serialize for i in items])


@app.route('/xml')
@app.route('/catalog/xml')
def indexXML():
    pass


@app.route('/atom')
@app.route('/catalog/atom')
def indexATOM():
    pass


if __name__ == "__main__":
    app.secret_key = '\x7f\x99\xe9\x91XjH?\x10\xe71\xa9My\x8d\xdb\xa2\xa8q0\xef\xda\x07\x8f'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
