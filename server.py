from flask import Flask, render_template, url_for, send_from_directory, request
from flask_socketio import SocketIO, emit, join_room, leave_room, close_room
import flask
from common import random_string, rps
from threading import Timer
import constants as cs

"""
Implemented a socket based approach for the rock-paper-scissor

It can easily be extended for multiple users. When a player creates a room,
a unique matchId is sent, and a new room(socket room) is created with that id.
Hence any number of people can join it later(for future implementations)



"""

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

users = set()  # set of unique users seen till now
rooms = {}  # contains keys as matchIds (see below)
"""
rooms = {
    "id1" : {
    "user1":choice,
    "user2":choice
    }
}
"""
play_stats = {}
"""
if wanted you can store room stats
"""


def send_result(roomId):
    """
    utility function to send the result of the match to a room
    """
    if roomId in rooms:
        data = [(user, choice) for user, choice in rooms[roomId].items()]
        if len(data) >= 2:
            result = rps.check(data[0][1], data[1][1])
            socketio.emit('result', {"data": data, "result": result},
                          room=roomId)


@app.route('/new_user')
def new_user():
    """
    create a unique user API
    """
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


@socketio.on(cs.NEW_MATCH)
def new_match(msg):
    """
    new_match request from a client
    return a matchId
    """
    user = msg['user']
    print 'new match for ' + user
    new_id = None
    while True:
        new_id = random_string()

        # If new_id already present then regenerate it
        if not rooms.get(new_id, None):
            break

    rooms[new_id] = {user: rps.none}
    join_room(new_id)
    emit(cs.NEW_MATCH, {"status": True, "matchId": new_id})


@socketio.on(cs.JOIN_MATCH)
def join_match(msg):
    """
    client provides an id to join a room
    """
    user = msg['user']
    roomId = msg['matchId']
    if rooms.get(roomId, None):
        if len(rooms[roomId].keys()) >= 2:
            emit(
                cs.JOIN_MATCH, {
                    "status": False, "text": "Already 2 people joined"})
            return
        if user in rooms[roomId]:
            emit(
                cs.JOIN_MATCH, {
                    "status": False, "text": "You've already joined previously in this room!"})
            return
        rooms[roomId][user] = rps.none
        join_room(roomId)

        emit('begin_match', {"users": rooms[roomId].keys()},
             room=roomId)
    else:
        emit(cs.JOIN_MATCH, {"status": False, "text": "Room doesn't exist"})


@socketio.on(cs.REMATCH)
def rematch(msg):
    """
    simple rematch implementation
    """
    user = msg['user']
    roomId = msg['matchId']
    join_room(roomId)
    emit(cs.REMATCH, room=roomId, include_self=False)


@socketio.on('play')
def play(msg):
    """
    play simulation. If both of them returned, then send the status
    """
    user = msg['user']
    roomId = msg['matchId']
    choice = msg['choice']

    rooms[roomId][user] = choice

    t = play_stats.get(roomId, None)
    if t and t == 1:
        send_result(roomId)
        play_stats[roomId] = 0
    else:
        play_stats[roomId] = 1


@socketio.on(cs.LEAVE)
def leave_match(msg):
    """
    If one of them, leaves broadcast the message to all members of room
    """
    user = msg['user']
    if 'matchId' in msg:
        roomId = msg['matchId']
        if user in rooms[roomId]:
            del rooms[roomId][user]

        leave_room(roomId)

        emit(cs.LEAVE, {"user": user}, room=roomId, include_self=False)

        if(len(rooms[roomId].keys()) == 0):
            close_room(roomId)
            del rooms[roomId]


if __name__ == '__main__':
    socketio.run(app, debug=True)
