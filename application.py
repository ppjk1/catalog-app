import datetime
from flask import Flask, session, redirect, render_template, request, url_for, flash, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dbsetup import Base, User, Category, Item

app = Flask(__name__)

engine = create_engine('sqlite:///catalog.db', echo=True)
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
dbsession = DBSession()


@app.route('/')
@app.route('/catalog')
def index():
    categories = dbsession.query(Category).all()
    return render_template('index.html', categories=categories)


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
    return jsonify(Categories=[c.serialize for c in categories])


@app.route('/catalog/<string:c_permalink>/json')
def showCategoryJSON(c_permalink):
    category = dbsession.query(Category).filter_by(permalink=c_permalink).one()
    items = dbsession.query(Item).filter_by(category_id=category.id)
    return jsonify(
        Category=category.name,
        Items=[i.serialize for i in items])


if __name__ == "__main__":
    app.secret_key = '\x7f\x99\xe9\x91XjH?\x10\xe71\xa9My\x8d\xdb\xa2\xa8q0\xef\xda\x07\x8f'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
