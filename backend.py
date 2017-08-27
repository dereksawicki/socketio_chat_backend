from flask import Flask, request, Response, jsonify
from flask_cors import CORS, cross_origin
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, send, emit, Namespace, join_room, leave_room, close_room
from models import db, Question, Blog_Post, Blog_PostDetail, AwolMessages
import time
from datetime import datetime
import json
from redis import Redis

 #connect to redis
redis_db = Redis() #connect to redis


app = Flask(__name__)
app.config['SECRET_KEY'] = 'Secret!'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:spoonlamp@127.0.0.1:5432/chat_db'

db.init_app(app)
socketio = SocketIO(app)
CORS(app)



# HTML API CALLS ----------------------------------------------
@app.route('/')
def hello():
	return jsonify( {'count': get_online_users()} ), 200


# Get all the posts
@app.route('/api/posts')
def get_posts():
	data = {}
	for post in Blog_Post.query.all():
		data[post.id] = {'title': post.title, 'snippet': post.snippet}
	return jsonify(data)

@app.route('/api/post/<int:postid>')
def get_post_detail(postid):
	post_detail = Blog_PostDetail.query.filter_by(post_id=str(postid)).first()
	if post_detail:
		data = {'body_text': post_detail.body_text}
		return jsonify(data)
	else:
		return jsonify("not found")

@app.route('/api/check_room/<room_id>')
def check_room(room_id):
	if isRoomEmpty(room_id):
		return jsonify({'empty': True})
	else:
		return jsonify({'empty': False})



# SOCKET IO --------------------------------------------------
# on connect, nothing happens
@socketio.on('connect', namespace='/chat')
def connect():
	emit('message', {'type': 'connect'})

# on connection
@socketio.on('connection', namespace='/chat')
def connection(data):
	cid = data['cid'];

	if not cid:
		mark_online(request.sid)
		emit('message', {'type':'cid', 'cid':request.sid})
		cid = request.sid

	# update redis
	old_sid = redis_db.get('client:%s:sid' % cid)
#	if old_sid:
#		redis_db.delete('sid:%s:cid' % old_sid)

	redis_db.set('sid:%s:cid' % request.sid, cid)
	redis_db.set('client:%s:sid' % cid, request.sid)

	# was the client awol?
	if redis_db.get('client:%s:awol' % cid):
		emit('message', {'type': 'welcome-back'})
		redis_db.delete('client:%s:awol' % cid)

		join_room(redis_db.get('client:%s:room_id' % cid))

		# send them their messages
		# get messages from postgres
		msgs = AwolMessages.get(cid)
		for msg in msgs:
			emit('message', {'type': 'pm', 'text': msg})

	# let client know they've connected
	emit('message', {'type':'connected'})
	emit_user_count()


# This function attempts to add the client making the request to a room with a 
# random partner that selected the opposite political leaning
# If no partner is available, the client is put on a waiting list
@socketio.on('get-partner', namespace='/chat')
def getPartner(data):

	cid = redis_db.get('sid:%s:cid' % request.sid).decode('utf-8')

	lean = data['lean']
	search = data['search']

	redis_db.set('client:%s:wait-list' % cid, '%s-waiting-%s' % (lean, search))

	room_id = cid

	list = ''
	# wants to match with left leaning user
	if search == "l":
		if lean == 'left':
			if redis_db.llen('left-waiting-l'):
				list = 'left-waiting-l'
			elif redis_db.llen('left-waiting-lr'):
				list = 'left-waiting-lr'
			else:
				redis_db.rpush('left-waiting-l', cid);
		elif lean == 'right':
			if redis_db.llen('left-waiting-r'):
				list = 'left-waiting-r'
			elif redis_db.llen('left-waiting-lr'):
				list = 'left-waiting-lr'
			else:
				redis_db.rpush('right-waiting-l', cid);
	elif search == "r":
		if lean == 'left':
			if redis_db.llen('right-waiting-l'):
				list = 'right-waiting-l'
			elif redis_db.llen('right-waiting-lr'):
				list = 'right-waiting-lr'
			else:
				redis_db.rpush('left-waiting-r', cid);
		elif lean == 'right':
			if redis_db.llen('right-waiting-r'):
				list = 'right-waiting-r'
			elif redis_db.llen('right-waiting-lr'):
				list = 'right-waiting-lr'
			else:
				redis_db.rpush('right-waiting-r', cid);
	else: # search is lr
		if lean == 'left':
			if redis_db.llen('right-waiting-l'):
				list = 'right-waiting-1'
			elif redis_db.llen('left-waiting-l'):
				list = 'left-waiting-l'
			elif redis_db.llen('right-waiting-lr'):
				list = 'right-waiting-lr'
			elif redis_db.llen('left-waiting-lr'):
				list = 'left-waiting-lr'
			else:
				redis_db.rpush('left-waiting-lr', cid);
		elif lean == 'right':
			if redis_db.llen('left-waiting-r'):
				list = 'left-waiting-r'
			elif redis_db.llen('right-waiting-r'):
				list = 'right-waiting-r'
			elif redis_db.llen('left-waiting-lr'):
				list = 'left-waiting-lr'
			elif redis_db.llen('right-waiting-lr'):
				list = 'right-waiting-lr'
			else:
				redis_db.rpush('right-waiting-lr', cid);

	if not list:
		emit('message', {'type': 'searching'});
	else: # match found
		# pop from left_waiting
		partner_cid = redis_db.lpop(list).decode('utf-8')


		# remove waiting list data
		redis_db.delete('client:%s:wait-list' % cid)
		redis_db.delete('client:%s:wait-list' % partner_cid)

		# generate a new room
		generateRoom(room_id, type=1)

		# add the pair to the room
		joinRoom(room_id=room_id, sid=request.sid)		
		joinRoom(room_id=room_id, sid=redis_db.get('client:%s:sid' % partner_cid).decode('utf-8'))




		redis_db.set('client:%s:pcid' % cid, partner_cid)
		redis_db.set('client:%s:pcid' % partner_cid, cid)

		# Give them their discussion topic
		id = int(redis_db.get('room:%s:topic_id' % room_id).decode('utf-8'))
		q = Question.get(id)
		emit('message', {'type':'q', 'question': q, 'id': id}, room=room_id)


		# Let clients know they've joined
		emit ('message', {'type':'matched'}, room=room_id)


	emit_user_count(True)


def generateRoom(room_id=None, type=1):
	# if no room id, generate a random one

	# set room type
	redis_db.set('room:%s:type' % room_id, type)

	# get topic id
	t_id = Question.getRandomIndex([])
	redis_db.rpush('room:%s:topics_seen' % room_id, t_id)
	
	redis_db.set('room:%s:topic_id' % room_id, t_id) 



# Let Client's partners know he wants a new question
@socketio.on('req-question', namespace='/chat')
def reqNewQuestion():
	cid = redis_db.get('sid:%s:cid' % request.sid).decode('utf-8')
	room_id = redis_db.get('client:%s:room_id' % cid).decode('utf-8')
	emit( 'message', {'type': 'rnq'}, room=room_id, include_self=False)


# Give the room a new question
@socketio.on('get-question', namespace='/chat')
def getNewRoomQuestion():
	cid     = redis_db.get('sid:%s:cid' % request.sid).decode('utf-8')
	room_id = redis_db.get('client:%s:room_id' % cid).decode('utf-8')

	used = redis_db.lrange('room:%s:topics_seen' % room_id, 0, -1)
	used = [ (int(x)) for x in used ]

	id = Question.getRandomIndex(used)
	q = Question.get(id)

	redis_db.set('room:%s:topic_id' % room_id, id)
	redis_db.rpush('room:%s:topics_seen' % room_id, id)

	emit('message', {'type': 'q', 'question': q, 'id': id}, room=room_id)

# join a room
def joinRoom(room_id, sid):
	# join the socket.io
	join_room(room_id, sid=sid)


	cid = redis_db.get('sid:%s:cid' % sid).decode('utf-8')

	# Update redis data
	redis_db.set('client:%s:room_id' % cid, room_id)

	# add cid to room
	redis_db.rpush('room:%s:cids' % room_id, cid) # add to room's user list


def isRoomEmpty(room_id):
	return redis_db.llen('room:%s:cids' % room_id) <= 0


# Client was trying to find a random parter. Remove from the waiting list.
@socketio.on('cj', namespace='/chat')
def cancelJoin():

	cid = redis_db.get('sid:%s:cid' % request.sid).decode('utf-8')

	wait_list = redis_db.get('client:%s:wait-list' % cid)
	if not wait_list:
		return

	redis_db.lrem(wait_list, cid)

	# remove client from waiting list
	redis_db.lrem(list, cid)
	redis_db.delete('client:%s:wait-list' % cid, list)

	emit_user_count(True)


# Client wants to leave a room. 
# If random room, close the room.
# If private group room and the room size is 0, close the room
# If this is a public community room, just remove client from the room.
@socketio.on('leave-room', namespace='/chat')
def leaveRoom(sid=None):
	if sid is None:
		sid = request.sid

	cid = redis_db.get('sid:%s:cid' % sid).decode('utf-8')

	# get the room data
	room_id = redis_db.get('client:%s:room_id' % cid).decode('utf-8')
	room_type = redis_db.get('room:%s:type' % room_id).decode('utf-8')

	# if this is a random room
	if room_type == '1':
		# Let connected clients know their partner has disconnected
		emit('message',\
			{'type': 'p-disconnect'}, room=room_id, include_self=False)

		# remove connected clients
		removeFromRoom(room_id, cid)
		partner_cid = redis_db.lpop('room:%s:cids' % room_id).decode('utf-8')
		removeFromRoom(room_id, partner_cid)

		# close the room
		closeRoom(room_id)

	emit_user_count(True)


# close a room and clean up related data
def closeRoom(room_id):
	# delete room data
	redis_db.delete('room:%s:type' % room_id,\
			'room:%s:cids' % room_id, \
			'room:%s:topic_id' % room_id,\
			'room:%s:topics_seen' % room_id)
	close_room(room_id, namespace='/chat')


# Remove sid from room room_id
def removeFromRoom(room_id, cid):
	sid = redis_db.get('client:%s:sid' % cid).decode('utf-8')

	leave_room(room_id, sid=sid, namespace='/chat')

	# remove client from room data
	redis_db.lrem('room:%s:cids' % room_id, cid)

	# delete client data
	redis_db.delete('client:%s:room_id' % cid, 'client:%s:pcid' % cid)



# user typing
# only used for type 1 (random) rooms
@socketio.on('ut', namespace='/chat')
def user_typing():
	data = {'type':'pt'}

	cid = redis_db.get('sid:%s:cid' % request.sid).decode('utf-8')

	room_id = redis_db.get('client:%s:room_id' % cid).decode('utf-8')

	emit('message', data, room=room_id, include_self=False)


# user not typing
# only used for type 1 (random) rooms
@socketio.on('unt',  namespace='/chat')
def user_not_typing():
	data = {'type':'pnt'}
	
	cid = redis_db.get('sid:%s:cid' % request.sid).decode('utf-8')

	room_id = redis_db.get('client:%s:room_id' % cid).decode('utf-8')

	emit('message', data, room=room_id, include_self=False)



# Should eventually just update every 7 seconds to all clients
@socketio.on('req-uc', namespace='/chat')
def emit_user_count(b=None):

	left_waiting = redis_db.llen('left-waiting-r') + redis_db.llen('left-waiting-l') + redis_db.llen('left-waiting-lr')
	right_waiting = redis_db.llen('right-waiting-r') + redis_db.llen('right-waiting-l') + redis_db.llen('right-waiting-lr')


	data = {'type': 'uc',\
		'left-waiting': left_waiting, \
		'right-waiting': right_waiting,\
		}

	if not b:
		emit('message', data)
	else:
		emit('message', data, broadcast=True)

# Difference from disconnect is that there is no possibility of being awol
@socketio.on('disconnection', namespace='/chat')
def disconnection(sid=None):
	if sid is None:
		sid = request.sid

	cancelJoin()

	# delete client data. Possibly redundant...
	cid = redis_db.get('sid:%s:cid' % sid).decode('utf-8')


	# if not awol, do a full disconnect
	if redis_db.get('client:%s:awol' % cid) is None:
		# get the room data
		room_id = redis_db.get('client:%s:room_id' % cid)
		if room_id:
			leaveRoom(sid)

		redis_db.delete('client:%s:sid' % cid, \
				'sid:%s:cid' % sid)



# Client has disconnected altogether. They left the page/
@socketio.on('disconnect', namespace='/chat')
def disconnect():
	cid = redis_db.get('sid:%s:cid' % request.sid).decode('utf-8')
	if not cid:
		return

	# If user currently in a room, theyve probably just gone awol
	room_id = redis_db.get('client:%s:room_id' % cid)
	if room_id:
		redis_db.set('client:%s:awol' % cid, 1)

	disconnection(request.sid)


# send message to all users in a room
@socketio.on('am', namespace='/chat')
def add_message(msg):
	cid = redis_db.get('sid:%s:cid' % request.sid).decode('utf-8')
	room_id = redis_db.get('client:%s:room_id' % cid).decode('utf-8')

	pcid = redis_db.get('client:%s:pcid' % cid).decode('utf-8')
	if not redis_db.get('client:%s:awol' % pcid):
		emit('message', {'text': msg['text'], \
			 'type': 'pm'},\
			 room=room_id, include_self=False)
	else:
		redis_db.incr('here')
		# add messages to postgres
		AwolMessages.add_msg(pcid, msg['text'])


# ONLINE USER COUNT HELPER METHODS
def mark_online(sid):
	now = int(time.time())
	expires = now + (5 * 60) + 10
	all_users_key = 'online-users/%d' % (now // 60)

	p = redis_db.pipeline()
	p.sadd(all_users_key, sid)
	p.expireat(all_users_key, expires)
	p.execute()


def get_online_users():
	current = int(time.time()) // 60
	minutes = range(5)
	union = redis_db.sunion(['online-users/%d' % (current - x) for x in minutes])
	return len(union)

if __name__ == '__main__':
	app.debug=True
	socketio.run(app, host='0.0.0.0')


