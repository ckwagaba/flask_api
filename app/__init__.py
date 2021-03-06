from flask_api import FlaskAPI
from flask_sqlalchemy import SQLAlchemy
from flask import request, jsonify, abort, render_template
import jwt
from flask_bcrypt import Bcrypt
from flask_cors import CORS, cross_origin

# in memory store for revoked tokens
revoked_tokens = []
version = '/v1'

# initialize sql-alchemy
"""
position of this import really matters
"""
db = SQLAlchemy()

# local import
from config import app_config
from app.models import *

def create_app(config_name):
    app = FlaskAPI(__name__, instance_relative_config=True)
    CORS(app)
    app.config.from_object(app_config[config_name])
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    """ landing page """
    @app.route('/')
    @app.route(version)
    def landing_page():
        return render_template('index.html')

    """create user"""
    @app.route(version + '/auth/register', methods=['POST'])
    def user_creation():
        try:
            email = request.data.get('email')
            password = request.data.get('password')
            # handle invalid input
            if email == None or password == None or not str(email).strip() or not str(password).strip():
                # no args
                return {'message': 'Enter valid input.'}, 400
            else:
                # check if user with email exists
                user = User.query.filter_by(email=email).first()
                if user:
                    return {"message": 'Email address already taken.'}, 409
                else:
                    user = User(email, password)
                    user.save()
                    return {"message": 'Account created successfully.'}, 201
        except Exception as e:
            return {"Error": e}

    """login user"""
    @app.route(version + '/auth/login', methods=['POST'])
    def user_login():
        email = request.data.get('email')
        password = request.data.get('password')
        if email == None or password == None or not str(email).strip() or not str(password).strip():
            # no args
            return {'message': 'Enter valid input.'}, 400
        else:
            # first check if user with email exists
            user = User.query.filter_by(email=request.data.get('email')).first()
            if user and user.password_is_valid(request.data.get('password')):
                # correct credentials
                # generate access token. this will be used as the authorization header
                access_token = user.generate_token(user.id)
                if access_token:
                    response = {
                        'message': 'You logged in successfully.',
                        'access_token': access_token.decode()
                    }, 200
                    return response
            else:
                # user does not exists
                response = {
                    'message': 'Verify credentials and try again.'
                }, 401
                return response

    """ logout user """
    @app.route(version + '/auth/logout', methods=['POST'])
    def user_logout():
        try:
            #get the access token from the request
            access_token = request.headers.get('Authorization')
            if access_token:
                revoked_tokens.append(access_token)
                return {'message': 'You logged out successfully'}, 200
        except Exception as e:
            # something went wrong on the server side
            return {'Error': e}

    """ change password """
    @app.route(version + '/auth/reset-password', methods=['POST'])
    def change_password():
        try:
            new_pass = request.data.get('password')
            # handle invalid input
            if new_pass == None or not str(new_pass).strip():
                # no args
                return {'message': 'Enter valid input'}, 400
            else:
                access_token = request.headers.get('Authorization')
                if access_token:
                    user_id = User.decode_token(access_token)
                    if not isinstance(user_id, str):
                        user = User.query.filter_by(id=user_id).first()
                        if user:
                            # hash new password
                            user.password = Bcrypt().generate_password_hash(password=new_pass).decode()
                            user.save()
                            revoked_tokens.append(access_token)
                            return {'message': 'Password changed successfully'}, 200
                else:
                    #user not legit
                    return {'Authentication': 'You are not authorized to access this page'}, 401

        except Exception as e:
            # something went wrong on the server side
            return {'Error': e}

    """create, and retrieve bucketlists"""
    @app.route(version + '/bucketlists/', methods=['POST', 'GET'])
    def bucketlists():
        try:
            # get the access token from the header
            access_token = request.headers.get('Authorization')
            if access_token and access_token not in revoked_tokens:
                # attempt to decode the token and get the user id
                user_id = User.decode_token(access_token)
                if not isinstance(user_id, str):
                    # returned ID is an int
                    # go ahead and handle the request, user is authenticated
                    if request.method == "POST":
                        # create bucketlists
                        name = request.data.get('name')
                        if name == None or not str(name).strip():
                            # handle invalid input
                            return {'message': 'Enter valid input'}, 400
                        else:
                            # saving bucketlists in lowercase
                            name = name.lower()
                            if name:
                                # check for duplicates for this bucketlist
                                bucketlist = Bucketlist.query.filter_by(name=name, user_id=user_id).first()
                                if bucketlist:
                                    return {'message': 'Duplicate entry'}, 409
                                else:
                                    bucketlist = Bucketlist(name=name, user_id=user_id)
                                    bucketlist.save()
                                    response = jsonify({
                                        'id': bucketlist.id,
                                        'name': bucketlist.name,
                                        'date_created': bucketlist.date_created,
                                        'date_modified': bucketlist.date_modified,
                                        'created_by': user_id
                                    })
                                    response.status_code = 201
                                    return response
                    else:
                        # GET all bucketlists
                        # get page, or use 1 as the default
                        page = request.args.get('page', 1, type=int)
                        # get value to be used for pagination
                        limit = request.args.get('limit', type=int) # you gotta stress the type
                        # get search term
                        search_query = request.args.get('q')
                        if search_query:
                            # convert term to lower case
                            search_query = search_query.lower()
                            bucketlists = Bucketlist.query.filter(Bucketlist.name.like('%' + search_query + '%')).filter_by(user_id=user_id).paginate(page, limit, False).items
                        else:
                            bucketlists = Bucketlist.query.filter_by(user_id=user_id).paginate(page, limit, False).items
                        results = []

                        for bucketlist in bucketlists:
                            obj = {
                                'id': bucketlist.id,
                                'name': bucketlist.name,
                                'date_created': bucketlist.date_created,
                                'date_modified': bucketlist.date_modified,
                                'created_by': user_id
                            }
                            results.append(obj)
                        all_results = {
                            'bucketlists_on_page': results,
                            'number_of_bucketlists_on_page': len(results)
                        }
                        response = jsonify(all_results)
                        response.status_code = 200
                        return response
                else:
                    # authentication failure
                    # user_id returns the output from the decode function
                    return {'Error': user_id}
            else:
                #user not legit
                return {'Authentication': 'You are not authorized to access this page'}, 401

        except Exception as e:
            # something went wrong on the server side
            return {'Error': e}

    """edit, delete bucketlist"""
    @app.route(version + '/bucketlists/<int:id>', methods=['GET', 'PUT', 'DELETE'])
    def bucketlist_manipulation(id, **kwargs):
        try:
            # get the access token from the header
            access_token = request.headers.get('Authorization')
            if access_token and access_token not in revoked_tokens:
                # attempt to decode the token and get the user id
                user_id = User.decode_token(access_token)
                if not isinstance(user_id, str):
                    # retrieve a buckelist using it's ID
                    bucketlist = Bucketlist.query.filter_by(id=id, user_id=user_id).first()
                    if not bucketlist:
                        return {
                            "message": "no bucketlist with id: {}".format(id)
                        }, 404

                    if request.method == 'DELETE':
                        # delete bucketlist
                        bucketlist.delete()
                        return {
                            "message": "bucketlist {} deleted successfully".format(bucketlist.id)
                         }, 200

                    elif request.method == 'PUT':
                        # edit bucketlist
                        name = request.data.get('name')
                        if name == None or not str(name).strip():
                            # handle invalid input
                            return {'message': 'Enter valid input'}, 400
                        else:
                            # saving bucketlists in lowercase
                            name = name.lower()
                            if name:
                                # check for duplicates for this bucketlist
                                other_bucketlist = Bucketlist.query.filter_by(name=name, user_id=user_id).first()
                                if other_bucketlist:
                                    return {'message': 'Duplicate entry'}, 409
                                else:
                                    bucketlist.name = name
                                    bucketlist.save()
                                    response = jsonify({
                                        'id': bucketlist.id,
                                        'name': bucketlist.name,
                                        'date_created': bucketlist.date_created,
                                        'date_modified': bucketlist.date_modified,
                                        'created_by': user_id
                                    })
                                    return response
                    else:
                        # GET bucketlist by id
                        response = jsonify({
                            'id': bucketlist.id,
                            'name': bucketlist.name,
                            'date_created': bucketlist.date_created,
                            'date_modified': bucketlist.date_modified,
                            'created_by': user_id
                        })
                        response.status_code = 200
                        return response
                else:
                    # authentication failure
                    return {'Error': user_id}
            else:
                return {'Authentication': 'You are not authorized to access this page'}, 401
        except:
            # user is not legit
            return {'Authentication': 'You are not authorized to access this page'}

    """ add and view items """
    @app.route(version + '/bucketlists/<int:id>/items/', methods=['POST', 'GET'])
    def add_item(id):
        try:
            # get the access token from the header
            access_token = request.headers.get('Authorization')
            if access_token and access_token not in revoked_tokens:
                # attempt to decode the token and get the user id
                user_id = User.decode_token(access_token)
                if not isinstance(user_id, str):
                    # returned ID is an int
                    # go ahead and handle the request, user is authenticated
                    if request.method == 'POST':
                        name = request.data.get('name')
                        if name == None or not str(name).strip():
                            # handle invalid input
                            return {'message': 'Enter valid input'}, 400
                        else:
                            # saving item in lowercase
                            name = name.lower()
                            if name:
                                # handle duplicate names first
                                other_item = Item.query.filter_by(name=name, bucketlist_id=id).first()
                                if other_item:
                                    return {'message': 'Duplicate entry'}, 409
                                else:
                                    item = Item(name=name, bucketlist_id=id)
                                    item.save()
                                    response = jsonify({
                                        'id': item.id,
                                        'name': item.name,
                                        'date_created': item.date_created,
                                        'bucketlist_id': id
                                    })
                                    response.status_code = 201
                                    return response
                    elif request.method == 'GET':
                        # get page, or use 1 as the default
                        page = request.args.get('page', 1, type=int)
                        # get value to be used for pagination
                        limit = request.args.get('limit', type=int)
                        # get search term
                        search_query = request.args.get('q')
                        if search_query:
                            # convert term to lower case
                            search_query = search_query.lower()
                            items = Item.query.filter(Item.name.like('%' + search_query + '%')).filter_by(bucketlist_id=id).paginate(page, limit, False).items
                        else:
                            items = Item.query.filter_by(bucketlist_id=id).paginate(page, limit, False).items
                        results = []
                        for item in items:
                            obj = {
                                'id': item.id,
                                'name': item.name,
                                'date_created': item.date_created,
                                'bucketlist_id': id
                            }
                            results.append(obj)
                        all_results = {
                            'bucketlist_items_on_page': results,
                            'number_of_bucketlist_items_on_page': len(results)
                        }
                        response = jsonify(all_results)
                        response.status_code = 200
                        return response
                else:
                    # authentication failure
                    # user_id returns the output from the decode function
                    return {'Error': user_id}
            else:
                return {'Authentication': 'You are not authorized to access this page'}, 401
        except Exception as e:
            return {'Error': e}

    """ edit and delete item """
    @app.route(version + '/bucketlists/<int:bucketlist_id>/items/<int:item_id>', methods=['GET', 'PUT', 'DELETE'])
    def item_edit_or_delete(bucketlist_id, item_id):
        try:
            # get the access token from the header
            access_token = request.headers.get('Authorization')
            if access_token and access_token not in revoked_tokens:
                # attempt to decode the token and get the user id
                user_id = User.decode_token(access_token)
                if not isinstance(user_id, str):
                    # returned ID is an int
                    # go ahead and handle the request, user is authenticated
                    this_bucketlist = Bucketlist.query.filter_by(id=bucketlist_id).first()
                    if this_bucketlist:
                        bucketlist_user_id = this_bucketlist.user_id
                        if bucketlist_user_id == user_id:
                            item = Item.query.filter_by(id=item_id, bucketlist_id=bucketlist_id).first()
                            if not item:
                                return {'message': 'No item with id {}'.format(item_id)}, 404
                            else:
                                if request.method == 'PUT':
                                    # edit item
                                    name = request.data.get('name')
                                    if name == None or not str(name).strip():
                                        # handle invalid input
                                        return {'message': 'Enter valid input'}, 400
                                    else:
                                        # handle duplicate names first
                                        other_item = Item.query.filter_by(name=name, bucketlist_id=bucketlist_id).first()
                                        if other_item:
                                            return {'message': 'Duplicate entry'}, 409
                                        else:
                                            # saving item in lowercase
                                            name = name.lower()
                                            if name:
                                                item.name = name
                                                item.save()
                                                response = jsonify({
                                                    'id': item.id,
                                                    'name': item.name,
                                                    'date_created': item.date_created,
                                                    'bucketlist_id': bucketlist_id
                                                })
                                                return response
                                elif request.method == 'DELETE':
                                    # delete item
                                    item.delete()
                                    return {'message': 'Item with id {} has been deleted.'.format(item_id)}, 200
                                else:
                                    # get item by ID
                                    response = jsonify({
                                        'id': item.id,
                                        'name': item.name,
                                        'date_created': item.date_created,
                                        'bucketlist_id': bucketlist_id
                                    })
                                    response.status_code = 200
                                    return response
                        else:
                            return {'Authentication': 'You are not authorized to access this page'}, 401
                else:
                    # authentication failure
                    # user_id returns the output from the decode function
                    return {'Authentication': 'You are not authorized to access this page'}, 401
            else:
                return {'Authentication': 'You are not authorized to access this page'}, 401
        except Exception as e:
            return {'Error': e}

    return app
