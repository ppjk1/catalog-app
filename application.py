from flask import Flask, session, redirect, render_template, request, url_for
app = Flask(__name__)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dbsetup import Base, User, Category, Item

engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
dbsession = DBSession()


@app.route('/')
def index():
    return render_template('categories.html')


@app.route('/catalog/<string:c_permalink>/items')
def showCategory(c_permalink):
    category = dbsession.query('Category').filter_by('c_permalink').one()
    return "This page will show all of the items for %s" % category.name


@app.route('/catalog/<string:c_permalink>/<i_permalink>')
def showItem(c_permalink, i_permalink):
    return "This page will display an item's details."


@app.route('/catalog/<string:i_permalink>/edit')
def editItem(i_permalink):
    return "This page will contain a form to edit an item."


@app.route('/catalog/<string:i_permalink>/delete')
def deleteItem(i_permalink):
    return "This page will contain a form to delete an item."



if __name__ == "__main__":
    app.secret_key = '\x7f\x99\xe9\x91XjH?\x10\xe71\xa9My\x8d\xdb\xa2\xa8q0\xef\xda\x07\x8f'
    app.debug = True
    app.run(host = '0.0.0.0', port = 8000)
