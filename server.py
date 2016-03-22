from flask import Flask, render_template,url_for, send_from_directory,request 
from flask_socketio import SocketIO, emit, join_room, leave_room, close_room
import flask
from common import random_string, rps
from threading import Timer

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

users = set()
rooms = {}
timers = {}
TIMEOUT = 5


def send_result(roomId):
    print 'send_result called'
    data = [(user,choice) for user, choice in rooms[roomId].items()]
    result = rps.check(data[0][1], data[1][1])
    print data, result
    socketio.emit('result', {"data": data, "result": result},
            room=roomId)


@app.route('/new_user')
def new_user():
    name = request.args.get('name')
    res = {}
    if name in users:
        res['text'] = "Name already exists"
        res['status'] = False
    else:
        users.add(name)
        res['text'] = "Created new user"
        res['status'] = True

    return flask.jsonify(**res)


@socketio.on('new_match')
def new_match(msg):

    user = msg['user']
    print 'new match for '+ user
    new_id = None
    while True:
        new_id = random_string()

        #If new_id already present then regenerate it
        if not rooms.get(new_id, None):
            break

    rooms[new_id] = {user: rps.none}
    join_room(new_id)
    emit('new_match', {"status": True, "matchId": new_id})
    


@socketio.on('join_match')
def join_match(msg):
    user = msg['user']
    roomId = msg['matchId']
    if rooms.get(roomId, None):
        if len(rooms[roomId].keys()) >= 2:
            emit('join_match', {"status": False, "text": "Already 2 people joined"})
            return

        rooms[roomId][user] = rps.none
        join_room(roomId)

        emit('begin_match', {"users": rooms[roomId].keys()},
            room=roomId)
    else:
        emit('join_match', {"status": False, "text": "Room doesn't exist"})

@socketio.on('rematch')
def rematch(msg):
    user = msg['user']
    roomId = msg['matchId']
    join_room(roomId)
    

@socketio.on('play')
def play(msg):
    user = msg['user']
    roomId = msg['matchId']
    choice = msg['choice']

    rooms[roomId][user] = choice

    t = timers.get(roomId,None)
    if t and t.isAlive():
        t.cancel()
        print 'stopping exisiting timer '
        send_result(roomId)
    else:
        print 'starting new timer'
        t = Timer(TIMEOUT, send_result, [roomId])
        t.start()
        timers[roomId] = t




@socketio.on('leave_match')
def leave_match(msg):
    user = msg['user']
    if 'matchId' in msg:
        roomId = msg['matchId']
        del rooms[roomId][user]

        leave_room(roomId)

        emit('leave_match', {"user": user}, room=roomId)

        if(len(rooms[roomId].keys()) == 0):
            close_room(roomId)
            del rooms[roomId]






if __name__ == '__main__':
    socketio.run(app, debug=True)