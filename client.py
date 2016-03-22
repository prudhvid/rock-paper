import os
import sys
from socketIO_client import SocketIO, LoggingNamespace
import requests
import json
import threading
import signal
from transitions import Machine

USER_FILE = './user.txt'
SERVER_IP = 'http://127.0.0.1'
SERVER_PORT = 5000

SERVER_ADDR = SERVER_IP + ":" + str(SERVER_PORT)

NEW_MATCH = 'new_match'
JOIN_MATCH = 'join_match'
BEGIN_MATCH = 'begin_match'
RESULT = 'result'
LEAVE = 'leave_match'

user_name = None
matchId = None





if not os.path.exists(USER_FILE):
    while True:
        print('please enter your nick:')
        nick = sys.stdin.readline()[:-1]
        args = {"name": nick}
        res = requests.get(SERVER_ADDR+"/new_user", params=args)
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


socketIO = SocketIO(SERVER_IP, SERVER_PORT, LoggingNamespace)




def get_msg(obj):
    if not matchId:
        user_obj = {
            "user": user_name
        }
    else:
        user_obj = {
            "user": user_name,
            "matchId": matchId
        }
    return  dict(obj, **user_obj)


    

def join_match():
    print 'Please enter matchId'
    matchID = sys.stdin.readline()[:-1]
    global matchId
    matchId = matchID
    msg = get_msg({})
    socketIO.emit(JOIN_MATCH, msg)
    

def main_loop():
    while True:
        print """
        What do you want to do?\n
        1. New Match
        2. Join Match
        3. Exit
        """
        c = sys.stdin.readline()
        if len(c) != 2 or c[0] < '1' or c[0] > '3':
            print 'Please enter correct value'
        else:
            c = int(c)
            if c == 1:
                new_match()
                break
            elif c==2:
                join_match()
                break
            else:
                print 'done'
                sys.exit(0)




def onjoin_match(msg):
    if msg:
        if not msg['status']:
            print msg['text']


        





def onleave(msg):
    print msg['user'] + " has left the match"

def exit_match(signal, frame):
    print 'leaving match!'
    socketIO.emit('leave_match', get_msg({}))
    socketIO.disconnect()
    sys.exit(0)
    



signal.signal(signal.SIGINT, exit_match)







class sm(object):
    
    states = ['dummy','init', 'waiting_join', 'playing', 'waiting_play', 'played', 'waiting_rematch', 
        'opp_exit', 'exit', 'joining']

    transitions = [
        {'trigger': 'new_match', 'source': 'init', 'dest': 'waiting_join'},
        {'trigger': 'join_match', 'source': 'init', 'dest': 'joining'},

        {'trigger': 'begin_match', 'source': 'waiting_join', 'dest': 'playing'},
        {'trigger': 'sent_value', 'source': 'playing', 'dest': 'waiting_play'},
        {'trigger': 'result', 'source': 'waiting_play', 'dest': 'played'},
        {'trigger': 'rematch', 'source': 'played', 'dest': 'waiting_rematch'},
        {'trigger': 'rematch_reply', 'source': 'waiting_rematch', 'dest': 'playing'},
        {'trigger': 'opp_exit', 'source': '*', 'dest': 'opp_exit'},
        {'trigger': 'exit', 'source': '*', 'dest': 'exit'}
    ]

    def __init__(self, name):
        self.name = name
        self.machine = Machine(model=self, states=sm.states, transitions=sm.transitions, initial='dummy')
        self.to_init()

    def on_enter_init(self):
        print """
        What do you want to do?\n
        1. New Match
        2. Join Match
        3. Exit
        """
        c = sys.stdin.readline()[0]
        if c == '1':
            msg = get_msg({})
            socketIO.emit(NEW_MATCH, msg)
        elif c == '2':
            print 'Please enter matchId'
            matchID = sys.stdin.readline()[:-1]
            global matchId
            matchId = matchID
            msg = get_msg({})
            socketIO.emit(JOIN_MATCH, msg)
        else:
            self.exit()

    def on_enter_exit(self):
        print 'leaving match!'
        socketIO.emit('leave_match', get_msg({}))
        socketIO.disconnect()
        sys.exit(0)

    def on_enter_waiting_join(self):
        print "Please share this id with your friend", matchId

    def on_enter_playing(self):
        print 'Enter your choice (R,P,S)'
        choice = sys.stdin.readline()[0]
        msg = get_msg({"choice":choice})
        socketIO.emit('play', msg)
        self.sent_value()

    def on_enter_result(self):
        print ("Do you want a rematch (y/n)?")
        ans = sys.stdin.readline()[0]
        if ans == 'y':
            print 'Waiting for other participant to join'
        else:
            self.exit()


    def sock_match_confirm(self, msg):
        if msg:
            if msg['status']:
                global matchId
                matchId = msg['matchId']
                self.new_match()
            else:
                print 'new_match failed'
                
    def sock_begin_match(self, msg):
        if msg:
            users = msg['users']
            print 'Match started between ' + users[0] + "and " + users[1]
            self.begin_match()
    def sock_onresult(self, msg):
        if msg:
            
            if msg['result'] == 0:
                print 'match drawn'
            elif msg['data'][0][0] == user_name and msg['result'] == 1\
                or msg['data'][1][0] == user_name and msg['result'] == -1:
                print "You've won the match"
            else:
                print "You've lost"
            self.result()
                

machine = sm("Test")















socketIO.on(JOIN_MATCH, onjoin_match)
socketIO.on(NEW_MATCH, machine.sock_match_confirm)
socketIO.on(BEGIN_MATCH, machine.sock_begin_match)
socketIO.on(RESULT, machine.sock_onresult)
socketIO.on(LEAVE, onleave)
# threading.Thread(target=main_loop).start()
# main_loop()
socketIO.wait(12000)