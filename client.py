import os
import sys
from socketIO_client import SocketIO, LoggingNamespace
import requests
import json
import threading
import signal
from transitions import Machine
import constants as cs

USER_FILE = './user.txt'
SERVER_IP = 'http://127.0.0.1'
SERVER_PORT = 5000

SERVER_ADDR = SERVER_IP + ":" + str(SERVER_PORT)


user_name = None
matchId = None


"""
Create a file USER_FILE in the current directory and use it afterwards
"""
if not os.path.exists(USER_FILE):
    while True:
        print('please enter your nick:')
        nick = sys.stdin.readline()[:-1]
        args = {"name": nick}
        res = requests.get(SERVER_ADDR + "/new_user", params=args)
        data = json.loads(res.content)

        if data['status']:
            with open(USER_FILE, 'w') as fobj:
                fobj.write(nick)
                user_name = nick
                break
        else:
            print data['text']
else:
    with open(USER_FILE) as fobj:
        user_name = fobj.readline()

# SocketIo for all communications with server
socketIO = SocketIO(SERVER_IP, SERVER_PORT, LoggingNamespace)


def get_msg(obj):
    """
        The default function used when communicating with server
        The obj is a dictionary and is appended to the basic data like user, matchId etc
    """
    if not matchId:
        user_obj = {
            "user": user_name
        }
    else:
        user_obj = {
            "user": user_name,
            "matchId": matchId
        }
    return dict(obj, **user_obj)


"""
    All interactions with server is designed as a State Machine
    The transitions are fairly self-explanatory
"""


class sm(object):

    states = [
        'dummy',
        'init',
        'waiting_join',
        'playing',
        'waiting_play',
        'played',
        'waiting_rematch',
        'opp_exit',
        'exit',
        'joining']

    transitions = [
        {'trigger': 'new_match', 'source': 'init', 'dest': 'waiting_join'},
        {'trigger': 'join_match', 'source': 'init', 'dest': 'waiting_join'},

        {'trigger': 'begin_match', 'source': 'waiting_join', 'dest': 'playing'},
        {'trigger': 'sent_value', 'source': 'playing', 'dest': 'waiting_play'},
        {'trigger': 'result', 'source': 'waiting_play', 'dest': 'played'},
        {'trigger': 'rematch', 'source': 'played', 'dest': 'waiting_rematch'},
        {'trigger': 'rematch_reply', 'source': 'waiting_rematch', 'dest': 'playing'},
        {'trigger': 'opp_exit', 'source': '*', 'dest': 'opp_exit'},
        {'trigger': 'exit', 'source': '*', 'dest': 'exit'}
    ]

    def __init__(self, name):
        """
        intializes the state machine with above transitions
        """
        self.opponent = None
        self.name = name
        self.machine = Machine(
            model=self,
            states=sm.states,
            transitions=sm.transitions,
            initial='dummy')
        self.to_init()

    def on_enter_init(self):
        """
        Default menu based input.
        After this, a confirmation from server will take us to next state

        """
        print """
        What do you want to do?\n
        1. New Match
        2. Join Match
        3. Exit
        """
        c = sys.stdin.readline()[0]
        if c == '1':
            msg = get_msg({})
            socketIO.emit(cs.NEW_MATCH, msg)
        elif c == '2':
            print 'Please enter matchId'
            matchID = sys.stdin.readline()[:-1]
            global matchId
            matchId = matchID
            msg = get_msg({})
            socketIO.emit(cs.JOIN_MATCH, msg)
            self.join_match()
        else:
            self.exit()

    def on_enter_exit(self):
        """
        Before leaving match, make sure you communicate it with server
        """
        print 'leaving match!'
        socketIO.emit(cs.LEAVE, get_msg({}))
        sys.exit(0)

    def on_enter_waiting_join(self):
        print "Please share this id with your friend", matchId

    def on_enter_playing(self):
        """
        The basic playing interface. Simple character based r,p,s
        """
        print 'Enter your choice Rock(r),Paper(p),Scissor(s)'
        choice = sys.stdin.readline()[0]
        if choice == 'r' or choice == 'p' or choice == 's':
            msg = get_msg({"choice": choice})
            socketIO.emit('play', msg)
            self.sent_value()
        else:
            print 'Wrong choice'
            self.on_enter_playing()

    def on_enter_played(self):
        """
        Rematch feature at the end of the game
        """
        print ("Do you want a rematch (y/n)?")
        ans = sys.stdin.readline()[0]
        if ans == 'y':
            print 'Waiting for other participant to join'
            socketIO.emit('rematch', get_msg({}))
            self.rematch()
        else:
            global matchId
            print 'leaving_match'
            socketIO.emit(cs.LEAVE, get_msg({}))
            matchId = None
            self.to_init()

    def on_enter_opp_exit(self):
        """
        opponent exited. Currently leaving from the game
        Might have better implementations
        """
        global matchId
        print self.opponent + ' has exited!'
        socketIO.emit(cs.LEAVE, get_msg({}))
        matchId = None
        self.to_init()

    def sock_match_confirm(self, msg):
        """
        Server responded with the matchId. Update the global matchId
        """
        if msg:
            if msg['status']:
                global matchId
                matchId = msg['matchId']
                self.new_match()
            else:
                print 'new_match failed'

    def sock_begin_match(self, msg):
        """
        Another player has joined the game
        """
        if msg:
            users = msg['users']
            print 'Match started between ' + users[0] + "and " + users[1]
            self.opponent = users[0] if users[1] == user_name else users[1]
            self.begin_match()

    def sock_onresult(self, msg):
        """
        Match ended.
        Calcuate the result and show.
        The server sends entire data. Its upto client to find out who won
        """
        if msg:
            user2 = msg['data'][1] if msg['data'][0][0] == user_name \
                else msg['data'][0]

            user1 = msg['data'][0] if msg['data'][0][0] == user_name \
                else msg['data'][1]

            print user2[0] + "has chose " + user2[1]
            if msg['result'] == 0:
                print 'match drawn'
            elif msg['data'][0][0] == user_name and msg['result'] == 1\
                    or msg['data'][1][0] == user_name and msg['result'] == -1:
                print "You've won the match"
            else:
                print "You've lost"
            self.result()

    def sock_onjoin_match(self, msg):
        """
            When using id to join a new game, server might respond with negative
            such as when room is already filled/ id previously used
        """
        if msg:
            if not msg['status']:
                global matchId
                print msg['text']
                matchId = None
                self.to_init()

    def sock_onrematch(self, msg):
        """
            rematch has been accepted by opponent too
        """
        self.rematch_reply()

    def sock_onleave(self, msg):
        """
            opponent has left
        """
        self.opp_exit()

machine = sm("Test")


def exit_match(signal, frame):
    machine.exit()


signal.signal(signal.SIGINT, exit_match)


socketIO.on(cs.JOIN_MATCH, machine.sock_onjoin_match)
socketIO.on(cs.NEW_MATCH, machine.sock_match_confirm)
socketIO.on(cs.BEGIN_MATCH, machine.sock_begin_match)
socketIO.on(cs.RESULT, machine.sock_onresult)
socketIO.on(cs.REMATCH, machine.sock_onrematch)
socketIO.on(cs.LEAVE, machine.sock_onleave)

socketIO.wait()
