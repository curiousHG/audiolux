from enum import Enum
from queue import Queue
from collections import deque

# color for printing in terminal
class Color:
    GREY = '\033[90m'
    YELLOW = '\033[33m'
    RED = '\033[31m'
    PINK = '\033[38;5;201m'
    GREEN = '\033[32m'
    LIGHT_BLUE = '\033[38;5;117m'
    BLUE = '\033[34m'
    ORANGE = '\033[38;5;208m'
    MAGENTA = '\033[35m'




class TextToColor:
    g = Color.GREY
    Y = Color.YELLOW
    R = Color.RED
    P = Color.PINK
    G = Color.GREEN
    b = Color.LIGHT_BLUE
    B = Color.BLUE
    O = Color.ORANGE
    M = Color.MAGENTA


class Tube:
    def __init__(self, max_capacity = 4):
        self.max_capacity = max_capacity
        self.tube = Queue()
        self.complete = False

    def is_full(self):
        return self.tube.qsize() == self.max_capacity
    
    def __repr__(self):
        return str(list(self.tube.queue))
    
    def is_empty(self):
        return self.tube.qsize() == 0
    
    def is_complete(self):
        # all colors in the tube are same and tube is full
        if self.is_full() and len(set(list(self.tube.queue))) == 1:
            return True
        return False
    
    def transfer_to(self, other_tube):
        """
            Transfer the top color from this tube to the other tube if possible. 
            Return True if the transfer was successful, False otherwise.

            If other tube is full, return False.
            If this tube is empty, return False.
            If other tube top color(index 0) is same as this tube top color(index 0) or other tube is empty, 
                transfer until the other tube is full and the top color of this tube is different from the top color of the other tube. 
        
        """
        if other_tube.is_full():
            return False
        if self.is_empty():
            return False
        if other_tube.is_empty() or other_tube.tube.queue[0] == self.tube.queue[0]:
            color_to_transfer = self.tube.queue[0]
            while not self.is_empty() and self.tube.queue[0] == color_to_transfer and not other_tube.is_full():
                # index 0 is the open/top end: balls are removed (get) AND added
                # (appendleft) there, so a poured ball stacks on top of the run.
                other_tube.tube.queue.appendleft(self.tube.get())
            return True
        return False

# read the input file and return a list of lines
def read_input_file(file_path):
    with open(file_path, 'r') as f:
        # first two numbers are number of testtubes and number of filled testtubes
        n, m = map(int, f.readline().strip().split())
        tubes = []
        # only m tubes are filled; read those, the remaining n - m start empty
        for _ in range(m):
            tubes.append(f.readline().strip())
        for _ in range(n - m):
            tubes.append('')
    return n, m, tubes


# --- solver helpers -------------------------------------------------------
# A search state is a tuple of tubes; each tube is a tuple of colors with
# index 0 = the open/top end (matching Tube's get/appendleft convention).

def _top_run(tube):
    """Return (top_color, run_length) for the consecutive run at the top."""
    color = tube[0]
    length = 1
    while length < len(tube) and tube[length] == color:
        length += 1
    return color, length


def _is_solved_state(state, capacity):
    """Solved when every tube is empty or full with a single color."""
    for tube in state:
        if tube and (len(tube) != capacity or len(set(tube)) != 1):
            return False
    return True


def _canonical(state):
    """Order-independent key: two states with the same multiset of tubes
    (just arranged differently) are equivalent."""
    return tuple(sorted(state))


def _apply_move(state, i, j, capacity):
    """Pour the top run of tube i onto tube j, returning the new state."""
    color, run = _top_run(state[i])
    amount = min(run, capacity - len(state[j]))
    new_state = list(state)
    new_state[i] = state[i][amount:]
    new_state[j] = (color,) * amount + state[j]
    return tuple(new_state)


def _legal_moves(state, capacity):
    """All useful pours, ordered so the most promising are tried first."""
    moves = []
    for i, src in enumerate(state):
        if not src:
            continue
        color, run = _top_run(src)
        # a tube that is already a single full color is done; never disturb it
        if len(src) == capacity and run == capacity:
            continue
        for j, dst in enumerate(state):
            if i == j or len(dst) >= capacity:
                continue
            if dst and dst[0] != color:
                continue
            # pouring a whole one-color tube into an empty tube makes no progress
            if not dst and run == len(src):
                continue
            moves.append((i, j))

    def priority(move):
        i, j = move
        dst = state[j]
        _, run = _top_run(state[i])
        space = capacity - len(dst)
        # prefer pouring onto a matching color, and pours that don't spill
        return (0 if dst else 1, 0 if run <= space else 1)

    moves.sort(key=priority)
    return moves




class GameState:
    def __init__(self, tubes, n, m):
        self.tubes = tubes
        self.n = n
        self.m = m

    def is_solved(self):
        for tube in self.tubes:
            if not tube.is_complete() and not tube.is_empty():
                return False
        return True
    
    def has_valid_moves(self):
        for i in range(self.n):
            for j in range(self.n):
                if i != j and self.tubes[i].transfer_to(self.tubes[j]):
                    return True
        return False
    
    def is_game_over(self):
        return self.is_solved() or not self.has_valid_moves()
    
    def state_hash(self):
        # create a hash of the current game state by concatenating the string representation of each tube
        state_string = ''
        for tube in self.tubes:
            state_string += str(tube) + '|'
        return hash(state_string)
    
    def solve(self):
        """
        Find the shortest sequence of moves that solves the puzzle.

        Returns a list of (from_index, to_index) tuples to apply in order, or
        None if the puzzle has no solution.

        Breadth-first search over an immutable snapshot of the state (index 0 of
        each tube = top), so the live Tube objects are left untouched. States are
        deduplicated by a canonical, order-independent key, so symmetric boards
        (same tube contents, different positions) are visited only once — this is
        the memoization that prevents revisiting states and bounds the search.
        BFS guarantees the first solution reached uses the fewest moves.
        """
        capacity = self.tubes[0].max_capacity if self.tubes else 4
        start = tuple(tuple(t.tube.queue) for t in self.tubes)

        if _is_solved_state(start, capacity):
            return []

        visited = {_canonical(start)}
        parent = {start: None}          # state -> (previous_state, move)
        frontier = deque([start])

        while frontier:
            state = frontier.popleft()
            for i, j in _legal_moves(state, capacity):
                nxt = _apply_move(state, i, j, capacity)
                key = _canonical(nxt)
                if key in visited:
                    continue
                visited.add(key)
                parent[nxt] = (state, (i, j))
                if _is_solved_state(nxt, capacity):
                    # walk the parent chain back to the start to recover moves
                    moves = []
                    node = nxt
                    while parent[node] is not None:
                        prev, move = parent[node]
                        moves.append(move)
                        node = prev
                    moves.reverse()
                    return moves
                frontier.append(nxt)

        return None
    
    def print(self):
        """
        Print the tubes in a vertical manner. 
        The top of the tube is printed at the top and the bottom of the tube is printed at the bottom. 

        # if the tube has less than 4 colors, print empty spaces for the remaining colors.   
        """

        vertical_tubes = []
        for tube in self.tubes:
            vertical_tube = []
            # if tube has less than 4 colors, first add empty spaces for the remaining colors and then add the colors of the tube.
            for _ in range(4 - tube.tube.qsize()):
                vertical_tube.append(' ')
            for color in tube.tube.queue:
                # print should have block of color instead of color character.
                vertical_tube.append(TextToColor.__dict__[color] + '█' + Color.GREY)
            vertical_tubes.append(vertical_tube)
        for i in range(4):
            for vertical_tube in vertical_tubes:
                if i < len(vertical_tube):
                    print(vertical_tube[i], end=' ')
                else:
                    print(' ', end=' ')
            print()
        print('-' * (self.n * 2 - 1))

    def transfer(self, from_tube_index, to_tube_index):
        from_tube = self.tubes[from_tube_index]
        to_tube = self.tubes[to_tube_index]
        return from_tube.transfer_to(to_tube)


if __name__ == '__main__':
    n, m, tubes = read_input_file('in.txt')

    tube_objects = []
    for tube in tubes:
        tube_object = Tube()
        for color in tube:
            tube_object.tube.put(color)
        tube_objects.append(tube_object)
    game_state = GameState(tube_objects, n, m)
    print('Initial board:')
    game_state.print()

    moves = game_state.solve()
    if moves is None:
        print('No solution exists for this puzzle.')
    else:
        print(f'Solved in {len(moves)} moves:')
        for step, (frm, to) in enumerate(moves, start=1):
            print(f'  {step:2}. tube {frm} -> tube {to}')
            game_state.transfer(frm, to)

        print('\nFinal board:')
        game_state.print()
        print('Solved!' if game_state.is_solved() else 'ERROR: not solved.')
