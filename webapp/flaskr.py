"""

The recommender system: The CookBook
authors : Michal Lukac, Boris Valentovic

"""

from random import randint
from mongokit import Connection
from flask import Flask, request, session, flash, redirect, url_for, render_template, make_response
from sqlalchemy import and_, or_
from models import recommender
from datetime import datetime
import base64
import json
import re

# allowed constants for file extension to database
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

# create our mongodb connection and register models
# this is our recommender computing database
mconnection = Connection()
mconnection.register([recommender.User])
mconnection.register([recommender.Recipe])
mconnection.register([recommender.NonPersonal])
userscol = mconnection['recsys'].users
recipecol = mconnection['recsys'].recipes
nonpcol = mconnection['recsys'].nonpersonal

# create our recsys app with flask framework
app = Flask(__name__)
app.config.from_object('config.Config')


def init_mongodb():
    recommender.init_mongodbnew(mconnection)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@app.before_request
def before_request():
    """
    Before every request we need to check if there is signed in user with session.

    :return: redirect to login page if user is not loged in
    """
    if 'logged_in' not in session and (request.endpoint != 'login' and request.endpoint != 'signup'):
        return redirect(url_for('login'))


@app.route('/', methods=['GET'])
def show_entries(entries=None, headline="Recipes"):
    """
    Show recipes on the webpage.

    :param entries: list of recipes
    :param headline: headline for page
    :return: rendered page with recipes
    """
    if entries == None:
      entries = recipecol.Recipe.find()
    return render_template('show_entries.html', entries=entries, headline="Recipes")


@app.route('/user/<login>', methods=['GET', 'POST'])
def show_profile(login):
    """
    Show profile of user by login id.

    :param login: unique login id of specific user
    :return: rendered page with user profile and similar people
    """
    user = userscol.User.find_one({'_id': login})
    simpeople_ids = user['similar_users']
    simpeople = []

    i = 0
    for user_id in simpeople_ids:
        simpeople.append(user_id['userid'])
        i += 1
        if i == 3: break

    return render_template('show_profile.html', user=userscol.User.find_one({'_id': login}), simpeople=simpeople)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login service stores session for user.

    :return: redirect to main page(success) or login again(fail)
    """
    error = None
    if request.method == 'POST':
        user = userscol.User.find_one({'_id': request.form['login'], 'password': request.form['password']})
        print user
        if user:
            session['logged_in'] = True
            session['user_in'] = request.form['login']
            flash('You were logged in as ' + request.form['login'])
            return redirect(url_for('show_entries'))
        else:
            error = 'Invalid username or password'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    """
    Logout from web application.

    :return: redirect to login.
    """
    session.pop('logged_in', None)
    session.pop('user_in', None)
    flash('You were logged out')
    return redirect(url_for('show_entries'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    Basic service for registration of new user.

    :return: form(fail) or redirect to login(success).
    """
    error = None
    if request.method == 'POST':
        try:
            # save document to mongodb
            user = userscol.User()
            user['_id'] = request.form['login']
            user['fullname'] = request.form['fullname']
            user['email'] = request.form['email']
            user['password'] = request.form['password']
            user.save()
            return redirect(url_for('login'))
        except Exception, e:
            error = "User already exists!"
            return render_template('signup.html', error=error)
    return render_template('signup.html', error=error)


@app.route('/user/<login>/cookbook', methods=['GET'])
def cookbook(login):
    """
    Cookbook of specific user.

    :param login: unique id of user
    :return: Rendered page with custom cookbook.
    """
    user = userscol.User.find_one({'_id': login})
    recipes = recipecol.Recipe.find({'$or': [{'userid': login}, {'_id': {'$in': user['favorites']}}]})
    headline = login + '\'s Cookbook'
    return render_template('show_entries.html', entries=recipes, headline=headline)


@app.route('/user/<login>/favorites', methods=['GET'])
def user_favorites(login):
    """
    Show favorite items of specific user.

    :param login: unique id of user
    :return: Rendered page with favorite items of specific user.
    """
    user = userscol.User.find_one({'_id': login})
    recipes = recipecol.Recipe.find({'id': {'$in': user['favorites']}})
    return render_template('show_profile.html', entries=recipes)


@app.route('/recipe/add', methods=['GET'])
def add():
    """
    Form for adding recipe.

    :return: Rendered page with form.
    """
    return render_template('add.html')


@app.route('/recipe/<id>/edit', methods=['GET'])
def edit(id):
    """
    Edit specific recipe through form.

    :param id:  unique id of recipe
    :return: Form for editing recipe.
    """
    entry = recipecol.Recipe.find_one({'_id': id})
    rec = recipecol.Recipe.find_one({'_id': int(id)})
    max = len(rec.get('ingredients'))

    if entry.userid != session['user_in']:
        return redirect(url_for('show_entries', headline="Recipes"))
    return render_template('edit.html', entry=entry, rec=rec, max=max, tags=','.join(rec['tags']))


@app.route('/recipe/add_entry', methods=['POST'])
def add_entry():
    """
    Add new recipe through post method to database.

    :return: redirect to main page.
    """
    # store the recipe
    tags = request.form['tags'].split(',')

    # create in mongo
    recipemongo = recipecol.Recipe()
    # recipemongo['_id'] = recipe.id
    recipemongo['userid'] = session['user_in']
    recipemongo['title'] = request.form['title']
    recipemongo['text'] = request.form['text']
    recipemongo['tags'] = tags
    recipemongo.save()

    # get ingredients
    count = 0
    nextIng = True

    # add to nonpersonal all tags
    data = nonpcol.NonPersonal.find_one({'_id': 1})

    for tag in tags:
        if tag not in data.get('tags'):
            data['tags'].append(unicode(tag))
    data.save()

    # and ingredients
    while nextIng:
        if 'ingredient_' + str(count) in request.form:
            name = request.form['ingredient_' + str(count)]
            amount = request.form['amount_' + str(count)]
            count += 1
            recipemongo['ingredients'].append({'ingredient': name, 'number': amount})
        else:
            print ("no more ingredients")
            nextIng = False

    recipemongo.save()
    flash('New entry was successfully posted')
    return redirect(url_for('show_entries', headline="Recipes"))


@app.route('/recipe/edit_entry', methods=['POST'])
def edit_entry():
    """
    Edit recipe in database through post method.

    :return: Redirect to main page.
    """
    recipemongo = recipecol.Recipe.find_one({'_id': int(request.form['id'])})
    recipemongo['tags'] = request.form['tags'].split(',')
    recipemongo['title'] = request.form['title']
    recipemongo['text'] = request.form['text']
    recipemongo['ingredients'] = []
    recipemongo.save()
    # get ingredients
    count = 0
    nextIng = True
    while nextIng:
        if 'ingredient_' + str(
                count) in request.form:  # a sucasne aj amount!!! + aj do add() -- alebo skor osefovat ze musi zadat
            name = request.form['ingredient_' + str(count)]
            amount = request.form['amount_' + str(count)]
            count += 1
            recipemongo['ingredients'].append({'ingredient': name, 'number': amount})
        else:
            print ("no more ingredients")
            nextIng = False
    recipemongo.save()
    return redirect(url_for('show_entries', headline="Recipes", tags=','.join(recipemongo['tags'])))


@app.route('/search/<text>', methods=['GET'])
def search(text=None):
    """
    Search recipes through mongo database on recipes.

    :param text: search string
    :return: Recipes with title similar to text param.
    """
    entries = recipecol.Recipe.find({'title': {'$regex': re.compile(text, re.IGNORECASE)}})
    return render_template('show_entries.html', entries=entries, headline="Recipes like " + text)


@app.route('/recipe/<id>', methods=['GET', 'POST'])
def show_entry(id):
    """
    Show entire recipe with steps, ingredients, ratings, sim. recipes.

    :param id: unique id of recipe
    :return: Rendered page with recipe.
    """
    canedit = None
    favorited = None

    # has user already faved the item?
    user = userscol.User.find_one({'_id': session['user_in'], 'favorites': int(id)})
    rated = userscol.User.find_one({'_id': session['user_in'], 'ratings.itemid': int(id)}, {'ratings.itemid': 1,
                                                                                            'ratings.value': 1,
                                                                                            '_id': 0})
    value = 0
    if rated:
        for item in rated.get('ratings'):
            if item.get('itemid') == int(id):
                value = item.get('value')

    # get tags
    rec = recipecol.Recipe.find_one({'_id': int(id)})
    tags = ','.join(rec['tags'])

    # now show similar recipes
    simrecipes_ids = rec['similar_items']
    simrecipes_t = []
    simrecipes_i = []
    for recipe_ in simrecipes_ids:
        if recipe_['type'] == 1:
            simrecipes_t.append(recipecol.Recipe.find_one({'_id': recipe_['itemid']}))
        else:
            simrecipes_i.append(recipecol.Recipe.find_one({'_id': recipe_['itemid']}))

    # if is users logged in recipe then he can edit it
    if user:
        favorited = True
    if rec['userid'] == session['user_in']:
        canedit = True
    return render_template('show_entry.html', canedit=canedit, favorited=favorited, value=value, rec=rec, tags=tags,
                           simrecipes_t=simrecipes_t, simrecipes_i=simrecipes_i)


# endregion

# region recommendations
@app.route('/recommend/topfav', methods=['GET'])
def topfav():
    """
    Show top favorited recipes.

    :return: page with most favorited recipes.
    """
    recipe = nonpcol.NonPersonal.find_one({'_id': 1})
    entries = recipecol.Recipe.find({'_id': {'$in': recipe['topfavorites']}})
    if entries == None: entries = []
    return render_template('show_entries.html', entries=entries, headline="Top favorites")


@app.route('/recommend/toprated', methods=['GET'])
def toprated():
    """
    Show top rated recipes.

    :return: page with top rated recipes.
    """
    recipe = nonpcol.NonPersonal.find_one({'_id': 1})
    entries = recipecol.Recipe.find({'_id': {'$in': recipe['toprated']}})
    print entries
    if entries == None: entries = []
    return render_template('show_entries.html', entries=entries, headline="Top rated")


@app.route('/user/<login>/recommend', methods=['GET'])
def recommend(login):
    """
    Recommend recipes for specific user based on his history.

    :param login: id of specific user
    :return: Page with recipes for selected user.
    """
    user = userscol.User.find_one({'_id': login})
    values = [predict['itemid'] for predict in user['predicted']]
    entries = recipecol.Recipe.find({'_id': {'$in': values}})

    # if there is no recommended recipes, get some random
    print entries.count()
    if entries.count() == 0:
        entries = []
        count = recipecol.Recipe.find().count()
        for i in range(1, 6):
            recipe = randint(1, count)
            entries.append(recipecol.Recipe.find_one({'_id': recipe}))
    return render_template('show_entries.html', entries=entries, headline="Recommended for you")


@app.route('/interesting', methods=['GET'])
def interesting():
    """
    Show Interesting recipes based on special formula.
    You can see the implementation in recengine.

    :return:
    """
    recipe = nonpcol.NonPersonal.find_one({'_id': 1})
    entries = recipecol.Recipe.find({'_id': {'$in': recipe['topinteresting']}})
    if entries == None: entries = []
    return render_template('show_entries.html', entries=entries, headline="Interesting")


@app.route('/recipes/<type>/<value>', methods=['GET'])
def show_recipes_adv(type=None, value=None, headline="Recipes"):
    if type == 'tags':  # tags
        entries = recipecol.Recipe.find({'tags': {'$in': [value]}})
        return render_template('show_entries.html', entries=entries, headline="Recipes in " + value)
    else:  # ingredients
        entries = recipecol.Recipe.find({'ingredients.ingredient': {'$in': [value]}})
        return render_template('show_entries.html', entries=entries, headline="Recipes in " + value)


@app.route('/api/favorite', methods=['POST'])
def favorite():
    """
    Rest api for ajax request to fav recipe.

    :return: Json with status OK
    """
    if request.method == "POST":
        # try:
        data = json.loads(request.data)
        if data['favorite'] == '1':
            # save to users
            user = userscol.User.find_one({'_id': data['userid']})
            user['favorites'].append(int(data['itemid']))
            user.save()
            # save to recipes
            recipe = recipecol.Recipe.find_one({'_id': int(data['itemid'])})
            recipe['favorites'].append(unicode(data['userid']))
            recipe.save()
        else:
            # and remove
            mconnection['recsys'].users.update({'_id': session['user_in']},
                                               {'$pull': {'favorites': int(data['itemid'])}})
            mconnection['recsys'].recipes.update({'_id': int(data['itemid'])},
                                                 {'$pull': {'favorites': data['userid']}})
        return json.dumps({'status': 'OK'})


@app.route('/api/rate', methods=['POST'])
def rate():
    """
    Rest api for ajax request to rate recipe.

    :return: json with status OK or ERR
    """
    if request.method == "POST":
        try:
            data = json.loads(request.data)
            # insert rating for user and item
            user = userscol.User.find_one({'_id': data['userid']})
            user['ratings'].append(
                {'itemid': data['itemid'], 'value': float(data['rating']), 'date_creation': datetime.now()})
            user.save()
            # user.print_ratings()
            return json.dumps({'status': 'OK'})
        except:
            return json.dumps({'status': 'ERR'})

# START
if __name__ == '__main__':
    init_mongodb()
    app.run()
