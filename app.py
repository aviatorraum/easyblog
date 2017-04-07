import os
import functools
import urllib
import re
import datetime
from flask import (Flask, flash, redirect, render_template, request,
                   Response, session, url_for)
from peewee import *
from playhouse.flask_utils import FlaskDB, get_object_or_404, object_list
from playhouse.sqlite_ext import *
from src.models import *

ADMIN_PASSWORD = '000000'
APP_DIR = os.path.dirname(os.path.realpath(__file__))
DATABASE = 'sqliteext:///%s' % os.path.join(APP_DIR, 'blog.db')
DEBUG = False
SECRET_KEY = 'shs#DhdH5HFf3j5^dr6gfGdm21g'
SITE_WIDTH = 800

app = Flask(__name__)
app.config.from_object(__name__)

# Defer initialization of the database.
db = FlaskDB(app)

# The `database` is the actual peewee database, as opposed to flask_db which is
# the wrapper.
# Ensure we can access the Model attribute.
database = db.database

@app.template_filter('clean_querystring')
def clean_querystring(request_args, *keys_to_remove, **new_values):
    querystring = dict((key, value) for key, value in request_args.items())
    for key in keys_to_remove:
        querystring.pop(key, None)
    querystring.update(new_values)
    return urllib.urlencode(querystring)

@app.errorhandler(404)
def not_found(exc):
    return Response(render_template('page_not_found.html')), 404

def login_required(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        if session.get('logged_in'):
            return fn(*args, **kwargs)
        return redirect(url_for('login', next=request.path))
    return inner

@app.route('/login/', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or request.form.get('next')
    if request.method == 'POST' and request.form.get('password'):
        password = request.form.get('password')
        if password == app.config['ADMIN_PASSWORD']:
            session['logged_in'] = True
            session.permanent = True  # Use cookie to store session.
            flash('You are now logged in.', 'success')
            return redirect(next_url or url_for('index'))
        else:
            flash('Incorrect password.', 'danger')
    return render_template('login.html', next_url=next_url)

@app.route('/logout/', methods=['GET', 'POST'])
def logout():
    if request.method == 'POST':
        session.clear()
        return redirect(url_for('login'))
    return render_template('logout.html')

@app.route('/')
def index():
    search_query = request.args.get('q')
    if search_query:
        query = Post.search(search_query)
    else:
        query = Post.public().order_by(Post.timestamp.desc())
    return object_list('index.html', query, search=search_query)

def _create_or_edit(post, template):
    if request.method == 'POST':
        post.title = request.form.get('title') or ''
        post.content = request.form.get('content') or ''
        post.published = request.form.get('published') or False
        if not (post.title and post.content):
            flash('Title and Content are required.', 'danger')
        else:
            # Wrap the call to save in a transaction so we can roll it back
            # cleanly in the event of an integrity error.
            try:
                with database.atomic():
                    post.save()
            except IntegrityError:
                flash('Error: this title is already in use.', 'danger')
            else:
                flash('Article saved successfully.', 'success')
                if post.published:
                    return redirect(url_for('detail', slug=post.slug))
                else:
                    return redirect(url_for('edit', slug=post.slug))
    return render_template(template, post=post)

@app.route('/create/', methods=['GET', 'POST'])
@login_required
def create():
    return _create_or_edit(Post(title='', content=''), 'create.html')

@app.route('/drafts/')
@login_required
def drafts():
    query = Post.drafts().order_by(Post.timestamp.desc())
    return object_list('index.html', query, check_bounds=False)

# article-title for url friendly
@app.route('/<slug>/')
def detail(slug):
    if session.get('logged_in'):
        query = Post.select()
    else:
        query = Post.public()
    post = get_object_or_404(query, Post.slug == slug)
    return render_template('detail.html', post=post)

@app.route('/<slug>/edit/', methods=['GET', 'POST'])
@login_required
def edit(slug):
    post = get_object_or_404(Post, Post.slug == slug)
    return _create_or_edit(post, 'edit.html')

# for pageination
@app.template_filter('clean_querystring')
def clean_querystring(request_args, *keys_to_remove, **new_values):
    querystring = dict((key, value) for key, value in request_args.items())
    for key in keys_to_remove:
        querystring.pop(key, None)
    querystring.update(new_values)
    return urllib.urlencode(querystring)

def main():
    database.connect()
    database.create_tables([Post, FTSPost], safe=True)
    app.run(debug=True)

if __name__ == '__main__':
    main()
