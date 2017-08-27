from flask_sqlalchemy import SQLAlchemy
from random import choice

db = SQLAlchemy()

# question database model
class Question(db.Model):
	__tablename__   = 'questions'
	id		= db.Column(db.Integer, primary_key=True)
	question	= db.Column(db.String(180))
	modtime		= db.Column(db.DateTime)

	def __init__(self, question):
		self.question = question


	@staticmethod
	def getRandomIndex(used):
		if len(used) >= 40:
			return  -1
		rand_index = choice([x for x in range(2,42) if x not in used])
		return rand_index

	@staticmethod
	def get(index):
		if index < 2 or index > 41:
			return 'bad request'
		else:
			return Question.query.filter_by(id=index).first().question

class AwolMessages(db.Model):
	__tablename__ 	= 'awol_messages'
	id		= db.Column(db.Integer, primary_key=True)
	sid		= db.Column(db.String(100))
	text		= db.Column(db.Text)

	def __init__(self, sid, text):
		self.sid  = sid
		self.text = text

	@staticmethod
	def get(cid):
		msgs = []
		for msg in AwolMessages.query.filter_by(sid=cid).all():
			msgs.append(msg.text)
			db.session.delete(msg)
		db.session.commit()
		return msgs


	@staticmethod
	def add_msg(cid, text):
		new_msg = AwolMessages(cid, text)
		db.session.add(new_msg)
		db.session.commit()


# blog post
class Blog_Post(db.Model):
	__tablename__   = 'posts'
	id		= db.Column(db.Integer, primary_key=True)
	title		= db.Column(db.String(255))
	snippet		= db.Column(db.String(255))
	modtime		= db.Column(db.DateTime)

	def __init__(self, title):
		self.title = title
()

# blog post detail
class Blog_PostDetail(db.Model):
	__tablename__   = 'post_details'
	id		= db.Column(db.Integer, primary_key=True)
	post_id		= db.Column(db.Integer, db.ForeignKey('posts.id'))
	body_text	= db.Column(db.Text)

	def __init__(self, post_id, body_text):
		self.post_id   = post_id
		self.body_text = body_text
