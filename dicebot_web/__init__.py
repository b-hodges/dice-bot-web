#!/usr/bin/env python3

import os
import datetime
import hashlib

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from sqlalchemy.orm.exc import NoResultFound

from .util import AUTHORIZATION_BASE_URL, TOKEN_URL, get_user, make_session
from .database import db, m
from .restful import api_bp
from .help import help_bp

# Create App
app = Flask(__name__)
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = None
# Attach Database and REST
db.init_app(app)
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(help_bp, url_prefix='/help')


def md5(filename):
    hasher = hashlib.md5()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


static_filename_chache = {}


def get_url(endpoint, *args, **kwargs):
    if endpoint == 'static':
        filename = kwargs.get('filename')
        if not filename:
            raise ValueError('No filename given to static endpoint')
        if filename not in static_filename_chache:
            static_filename_chache[filename] = md5(os.path.join(app.root_path, 'static', filename))
        kwargs['md5'] = static_filename_chache[filename]
    return url_for(endpoint, *args, **kwargs)


# ----#-   Application


def create_app():
    '''
    Sets up app for use
    Adds database configuration and the secret key
    '''
    if app.config['SQLALCHEMY_DATABASE_URI'] is not None:
        # setup config values
        with app.app_context():
            db.create_all()
            # these settings are stored in the configuration table
            # values here are defaults (and should all be strings or null)
            # defaults will autopopulate the database when first initialized
            # when run subsequently, they will be populated from the database
            # only populated on startup, changes not applied until restart
            config = {
                # key used to encrypt cookies
                'token': None,
                # discord oauth2 id and secret
                'discord_client_id': None,
                'discord_client_secret': None,
                # cookie lifetime in days
                'PERMANENT_SESSION_LIFETIME': '1',
            }
            # get Config values from database
            for name in config:
                try:
                    key = db.session.query(m.Config).filter_by(name=name).one()
                    config[name] = key.value
                except NoResultFound:
                    key = m.Config(name=name, value=config[name])
                    db.session.add(key)
                    db.session.commit()
            app.config.update(config)
            app.config['PERMANENT_SESSION_LIFETIME'] = \
                datetime.timedelta(int(app.config['PERMANENT_SESSION_LIFETIME']))
            app.secret_key = app.config['token']


@app.before_request
def make_session_permanent():
    session.permanent = True


@app.context_processor
def context():
    '''
    Makes extra variables available to the template engine
    '''
    permissions = (
        0x00000040 |  # add reactions
        0x00000400 |  # view channel
        0x00000800 |  # send messages
        0x00002000 |  # manage messages
        0x00004000 |  # embed links
        0x00008000 |  # attach files
        0x00010000 |  # read message history
        0x00020000 |  # mention everyone
        0x00040000 |  # use external emojis
        0x04000000 |  # change nicknames
        0x10000000    # manage roles
    )
    invite_url = '{}?client_id={}&scope=bot&permissions={}'.format(
        AUTHORIZATION_BASE_URL, app.config['discord_client_id'], permissions)
    return {'invite_url': invite_url, 'url_for': get_url}


# ----#-   Errors


def error(e, message=None):
    '''
    Basic error template for all error pages
    '''
    user, discord = get_user(session.get('oauth2_token'))
    html = render_template(
        'error.html',
        user=user,
        title=str(e),
        message=message,
    )
    return html


@app.errorhandler(400)
def four_hundred(e):
    '''
    400 (bad request) error page
    '''
    return error(e), 400


@app.errorhandler(403)
def four_oh_three(e):
    '''
    403 (forbidden) error page
    '''
    return error(e), 403


@app.errorhandler(404)
def four_oh_four(e):
    '''
    404 (page not found) error page
    '''
    return error(e), 404


@app.errorhandler(500)
def five_hundred(e):
    '''
    500 (internal server) error page
    '''
    message = '500 Internal Server Error: Whoops, looks like something went wrong!'
    return error(message), 500


@app.route('/error/<int:error>')
def doError(error):
    '''
    For testing purposes, allows easy testing of error messages
    '''
    abort(error)


# ----#-   Pages


@app.route('/favicon.ico')
def favicon():
    '''
    The favorites icon for the site
    '''
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'images'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon',
    )


@app.route('/node_modules/<path:filename>')
def node_modules(filename):
    return send_from_directory(os.path.join(app.root_path, '..', 'node_modules'), filename)


views = {
    '/': ([], ['react-utils.js', 'index.js']),
    '/character': (
        ['remarkable/dist/remarkable.min.js'],
        ['react-utils.js', 'character.js']
    ),
    '/character-list': ([], ['react-utils.js', 'character-list.js']),
    '/character-select': ([], ['react-utils.js', 'character-select.js']),
}


@app.route('/')
def index():
    '''
    Homepage for the bot
    '''
    return react_view()


def react_view():
    '''
    Renders a template with the given react scripts loaded
    '''
    user, discord = get_user(session.get('oauth2_token'))
    js, jsx = views[request.path]
    return render_template('react.html', user=user, js=js, jsx=jsx)


for rule in views:
    app.add_url_rule(rule, view_func=react_view)


# ----#-   Login/Logout


@app.route('/login/')
def login():
    '''
    Redirects the user to the Discord sign in page
    '''
    scope = request.args.get('scope', 'identify guilds')
    discord = make_session(scope=scope.split(' '))
    authorization_url, state = discord.authorization_url(AUTHORIZATION_BASE_URL)
    session['oauth2_state'] = state
    return redirect(authorization_url)


@app.route('/callback')
def callback():
    '''
    Logs the user in using the OAuth API
    '''
    if request.values.get('error'):
        return request.values['error']
    discord = make_session(state=session.get('oauth2_state'))
    token = discord.fetch_token(
        TOKEN_URL,
        client_secret=app.config['discord_client_secret'],
        authorization_response=request.url)
    user, discord = get_user(token=token)
    blacklisted = db.session.query(m.Blacklist).get(int(user['id']))
    if not blacklisted:
        session['oauth2_token'] = token
        return redirect(url_for('index'))
    else:
        abort(403)


@app.route('/logout/')
def logout():
    '''
    Logs the user out and returns them to the homepage
    '''
    session.clear()
    flash(
        '&#10004; Successfully logged out. ' +
        'You will need to log out of Discord separately.')
    return redirect(url_for('index'))


# ----#-   Main

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB', None)
create_app()
