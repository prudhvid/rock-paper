import random


class rps:
    """
    class for rock paper scisssor
    """
    rock = 'r'
    paper = 'p'
    scissor = 's'
    none = 'n'

    wins_against = {
        paper: [rock, none],
        rock: [scissor, none],
        scissor: [paper, none],
        none: []
    }

    @staticmethod
    def check(p1, p2):
        """
        checks for win, returns 
        1 if p1 wins
        0 if draw
        -1 if p2 wins

        """
        if p1 == p2:
            return 0
        else:
            if p1 in rps.wins_against[p2]:
                return -1
            elif p2 in rps.wins_against[p1]:
                return 1
            else:
                return 0


def random_string():
    """
    To create matchIds
    """
    n = 10

    lower = "abcdefghijklmnopqrstuvwxyz"
    digits = "0123456789"

    return "".join(random.choice(lower + digits) for _ in range(n))
