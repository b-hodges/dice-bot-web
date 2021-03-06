import os
import time

import requests
from flask import current_app, abort, session, url_for
from requests_oauthlib import OAuth2Session

# Configure Discord OAuth
API_BASE_URL = 'https://discordapp.com/api'
AUTHORIZATION_BASE_URL = API_BASE_URL + '/oauth2/authorize'
TOKEN_URL = API_BASE_URL + '/oauth2/token'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'  # possibly insecure


def token_updater(token):
    session['oauth_token'] = token


def make_session(token=None, state=None, scope=None):
    client_id = current_app.config['discord_client_id']
    client_secret = current_app.config['discord_client_secret']
    callback = url_for('callback', _external=True, _scheme='http' if current_app.debug else 'https')
    return OAuth2Session(
        client_id=client_id,
        token=token,
        state=state,
        scope=scope,
        redirect_uri=callback,
        auto_refresh_kwargs={
            'client_id': client_id,
            'client_secret': client_secret,
        },
        auto_refresh_url=TOKEN_URL,
        token_updater=token_updater,
    )


def get_user(token=None):
    discord = make_session(token=token)
    user = user_get(discord, API_BASE_URL + '/users/@me').json()
    return user if 'id' in user else None, discord


def user_get(discord, url):
    '''
    A get request authenticated by the user token
    Handles rate limiting
    '''
    response = discord.get(url)
    while response.status_code == 429:
        ms = response.json().get('retry_after', 1000) + 5
        time.sleep(ms / 1000)
        response = discord.get(url)
    return response


def bot_get(url):
    '''
    A get request authenticated by the bot
    Handles rate limiting
    '''
    response = requests.get(url, headers={'Authorization': 'Bot ' + current_app.config['token']})
    while response.status_code == 429:
        ms = response.json().get('retry_after', 1000) + 5
        time.sleep(ms / 1000)
        response = requests.get(url, headers={'Authorization': 'Bot ' + current_app.config['token']})
    return response


def user_in_guild(guild, user):
    '''
    Returns whether the given user is in the given guild
    Both guild and user should be the respective IDs
    '''
    return bot_get(API_BASE_URL + '/guilds/{}/members/{}'.format(guild, user))


def get_guild(guild):
    '''
    Gets a guild object
    '''
    resp = bot_get(API_BASE_URL + '/guilds/{}'.format(guild))
    if not resp:
        abort(resp.status_code)
    return resp.json()


def user_is_admin(guild, user):
    '''
    Returns whether the user is an admin in the given guild
    Guild may be the guild object or the guild's ID
    User may be the member object or their ID
    '''
    if isinstance(guild, str):
        guild = get_guild(guild)
    owner_id = guild.get('owner_id', 'no owner')
    if isinstance(user, str):
        if owner_id == user:
            return True
        user = get_user(guild['id'], user)
    elif owner_id == user.get('user', user).get('id', 'no id'):
        return True
    roles = {role['id']: role for role in guild.get('roles', [])}
    for role in user.get('roles', []):
        if roles.get(role, {}).get('permissions', 0) & 0x00000008:
            return True
    return False


def bot_in_guild(guild):
    '''
    Returns whether the bot is in the given guild
    The guild should be a dict as returned by discord Guild resources
    '''
    guild = bot_get(API_BASE_URL + '/guilds/{}'.format(guild.get('id')))
    return bool(guild)
